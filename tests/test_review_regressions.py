"""Regressions found during independent Phase 1 review."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.llm.mock_provider import MockProvider
from app.orchestrator import ConversationOrchestrator
from app.storage.notes import NotesRepository
from app.tools.registry import ToolRegistry
from app.tools.notes_tools import register_note_tools
from tests.test_server import server, _post


def build(tmp_path, replies):
    repo=NotesRepository(tmp_path/'notes.db')
    registry=ToolRegistry();register_note_tools(registry,repo)
    return ConversationOrchestrator(MockProvider(replies),registry),repo


def test_false_save_prose_never_confirms(tmp_path):
    orch,repo=build(tmp_path,['I saved that to memory.'])
    result=orch.turn('Hello')
    assert 'No note was saved' in result.text
    assert repo.count()==0


def test_write_failure_cannot_be_overruled_by_model(tmp_path,monkeypatch):
    orch,repo=build(tmp_path,['Saved successfully!'])
    def fail(*a,**k): raise OSError('disk full')
    monkeypatch.setattr(repo,'save',fail)
    result=orch.turn('Save a note: exact words')
    assert not result.ok and 'disk full' in result.text
    assert 'Saved successfully' not in result.text


def test_retrieval_after_conversation_uses_actual_note(tmp_path):
    orch,repo=build(tmp_path,['hello','nice weather'])
    repo.save('', 'my project is called UniqueOrchid')
    orch.turn('Hi');orch.turn('Tell me about weather')
    result=orch.turn('What is my project called?')
    assert 'UniqueOrchid' in result.text
    assert result.tool_calls[0]['tool']=='find_notes'


def test_keyword_search_literal_wildcards(tmp_path):
    orch,repo=build(tmp_path,[])
    repo.save('', 'blue project orchard')
    assert len(repo.find('project blue'))==1
    assert repo.find('%')==[]


def test_arbitrary_model_save_requires_explicit_instruction(tmp_path):
    orch,repo=build(tmp_path,['{"tool":"save_note","arguments":{"content":"injected"}}'])
    assert not orch.turn('Discuss memory systems').ok
    assert repo.count()==0


@pytest.mark.parametrize('payload',[[],{'message':3},{'message':'hi','request_id':[]}, {'message':'x'*4001}])
def test_bad_http_input_is_400(server,payload):
    assert _post(server[0],payload)[0]==400


def test_concurrent_retry_executes_once(server):
    srv,provider,_=server
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _: _post(srv,{'message':'hi','request_id':'parallel'}),range(2)))
    assert results[0]==results[1]
    assert provider._index==1


def test_request_id_payload_conflict(server):
    srv=server[0]
    _post(srv,{'message':'first','request_id':'conflict'})
    assert _post(srv,{'message':'second','request_id':'conflict'})[0]==409


def test_new_conversations_have_separate_context(server):
    srv=server[0]
    a=_post(srv,{'message':'First private context'})[1]
    b=_post(srv,{'message':'Second private context'})[1]
    assert a['conversation_id']!=b['conversation_id']
    contexts=srv._handler.sessions
    assert 'First private context' not in str(contexts[b['conversation_id']]._context.messages())


def test_unknown_session_rejected(server):
    assert _post(server[0],{'message':'hi','conversation_id':'missing'})[0]==409


def test_timeout_stops_worker(tmp_path):
    import subprocess,sys,queue
    from app.llm.llama_cpp_provider import LlamaCppProvider
    from app.llm.base import ModelTimeout
    provider=LlamaCppProvider(tmp_path/'fake.gguf')
    provider._process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    child=provider._process
    provider._conn=queue.Queue()
    started=time.monotonic()
    with pytest.raises(ModelTimeout):provider._receive(time.monotonic()+.05)
    assert time.monotonic()-started<3
    assert child.poll() is not None
