"""Orchestration: tool loop, error handling, bounded context, idempotency."""

import pytest

from app.llm.base import ModelUnavailable
from app.llm.mock_provider import MockProvider
from app.orchestrator import ConversationOrchestrator, extract_tool_call
from app.storage.notes import NotesRepository
from app.tools.notes_tools import register_note_tools
from app.tools.registry import ToolRegistry


def make_orchestrator(replies, tmp_path, **kwargs):
    repo = NotesRepository(tmp_path / "orch.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    provider = MockProvider(replies=replies)
    kwargs.setdefault("max_tool_iterations", 4)
    return ConversationOrchestrator(provider, registry, **kwargs), repo


def test_extract_tool_call_minimal():
    assert extract_tool_call('{"tool": "save_note", "arguments": {"content": "x"}}') == {
        "tool": "save_note",
        "arguments": {"content": "x"},
    }


def test_extract_tool_call_with_surrounding_text():
    text = 'Sure, saving.\n{"tool": "find_notes", "arguments": {"query": "project"}}'
    call = extract_tool_call(text)
    assert call["tool"] == "find_notes"


def test_extract_tool_call_fenced_json():
    text = 'Will do.\n```json\n{"tool": "save_note", "arguments": {"content": "x"}}\n```'
    call = extract_tool_call(text)
    assert call["tool"] == "save_note"


def test_extract_tool_call_none_when_plain_text():
    assert extract_tool_call("hello there, how can I help?") is None


def test_extract_tool_call_malformed():
    from app.llm.base import ModelOutputError

    with pytest.raises(ModelOutputError):
        extract_tool_call('{"tool": "save_note", "arguments": ')


def test_extract_tool_call_qwen_native_format():
    """Qwen 2.5 native tool calls arrive as <tool_call> with double-braced JSON."""
    text = '<tool_call>\n{{"name": "find_notes", "arguments": {"query": "project"}}}\n</tool_call>'
    assert extract_tool_call(text) == {
        "tool": "find_notes",
        "arguments": {"query": "project"},
    }


def test_extract_tool_call_qwen_native_save():
    text = '<tool_call>{{"name": "save_note", "arguments": {"content": "my project is called Vamsi Companion.", "title": "Vamsi Companion Note"}}}</tool_call>'
    assert extract_tool_call(text) == {
        "tool": "save_note",
        "arguments": {"content": "my project is called Vamsi Companion.",
                      "title": "Vamsi Companion Note"},
    }


def test_extract_openai_style_name_arguments():
    text = '{"name": "find_notes", "arguments": {"query": "project"}}'
    assert extract_tool_call(text) == {
        "tool": "find_notes",
        "arguments": {"query": "project"},
    }


def test_save_note_round_trip_via_model(tmp_path):
    tool_reply = '{"tool": "save_note", "arguments": {"title": "T", "content": "my project is called Vamsi Companion"}}'
    orch, repo = make_orchestrator([tool_reply, "Saved it!"], tmp_path)
    turn = orch.turn("Save a note: my project is called Vamsi Companion.")
    assert turn.ok is True
    assert turn.tool_calls == [{"tool": "save_note",
                                "arguments": {"content": "my project is called Vamsi Companion."}}]
    assert "Saved note:" in turn.text
    assert repo.count() == 1


def test_voice_style_save_note_without_colon(tmp_path):
    orch, repo = make_orchestrator([], tmp_path)
    turn = orch.turn("save a note my project is called Vamshi competition")
    assert turn.ok is True
    assert turn.tool_calls == [{"tool": "save_note",
                                "arguments": {"content": "my project is called Vamshi competition"}}]
    assert "Saved note:" in turn.text
    assert repo.find("Vamshi competition")[0].content == "my project is called Vamshi competition"


def test_find_notes_grounded_in_storage(tmp_path):
    orch, repo = make_orchestrator([], tmp_path)
    repo.save("Projects", "my project is called Vamsi Companion")
    replies = [
        '{"tool": "find_notes", "arguments": {"query": "project"}}',
        "Vamsi Companion is the name of your project.",
    ]
    orch2, _ = make_orchestrator(replies, tmp_path)
    turn = orch2.turn("What is my project called?")
    assert turn.ok is True
    assert "Vamsi Companion" in turn.text
    assert turn.tool_calls[0]["tool"] == "find_notes"


def test_invalid_tool_name_reported_honestly(tmp_path):
    replies = ['{"tool": "delete_everything", "arguments": {}}', "That tool isn't allowed, so I didn't run it."]
    orch, _ = make_orchestrator(replies, tmp_path)
    turn = orch.turn("Do the bad thing")
    assert turn.ok is False
    assert "unknown tool" in turn.text
    assert turn.tool_calls == [{"tool": "delete_everything", "arguments": {}}]


def test_invalid_arguments_reported_honestly(tmp_path):
    replies = ['{"tool": "save_note", "arguments": {"no_content_here": "x"}}', "I couldn't save that; it needs content."]
    orch, _ = make_orchestrator(replies, tmp_path)
    turn = orch.turn("save something")
    assert turn.ok is False
    assert _.count() == 0


def test_model_unavailable_returns_error_turn(tmp_path):
    provider = MockProvider(available=False, reason="model file not found")
    repo = NotesRepository(tmp_path / "u.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    orch = ConversationOrchestrator(provider, registry)
    turn = orch.turn("hello")
    assert turn.ok is False
    assert "model" in turn.error.lower() or "ModelUnavailable" in turn.error


def test_empty_model_output_handled(tmp_path):
    """Empty output produces ModelOutputError; orchestrator must not crash and
    must not pretend success."""

    class _EmptyProvider:
        name = "empty"

        def is_available(self):
            return True

        def generate(self, messages, **kwargs):
            from app.llm.base import ModelOutputError

            raise ModelOutputError("model returned empty output")

    repo = NotesRepository(tmp_path / "e.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    orch = ConversationOrchestrator(_EmptyProvider(), registry, max_tool_iterations=2)
    turn = orch.turn("hello")
    assert turn.ok is False
    assert turn.text  # a message exists, not a crash


def test_bounded_tool_loop(tmp_path):
    """A model that keeps requesting tools must be stopped by iteration bound."""
    calls = {"n": 0}

    class _LoopProvider:
        name = "loop"

        def is_available(self):
            return True

        def generate(self, messages, **kwargs):
            calls["n"] += 1
            return '{"tool": "save_note", "arguments": {"content": "x"}}'

    repo = NotesRepository(tmp_path / "l.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    orch = ConversationOrchestrator(_LoopProvider(), registry, max_tool_iterations=3)
    turn = orch.turn("go")
    assert calls["n"] == 1
    assert turn.ok is False
    assert repo.count() == 0


def test_conversation_context_bounded(tmp_path):
    orch, _ = make_orchestrator(["hi", "there", "yo"], tmp_path, max_turns=2, max_tool_iterations=1)
    for msg in ["a", "b", "c", "d", "e", "f"]:
        orch.turn(msg)
    # The system prompt plus <= max_turns*2 non-system messages remain.
    msgs = orch._context.messages()
    non_system = [m for m in msgs if m["role"] != "system"]
    assert len(non_system) <= 4


def test_duplicate_save_via_retry_request(tmp_path):
    """Retrying the same user request with the same content must not create
    duplicate note rows (fingerprint dedupe inside storage)."""
    orch, repo = make_orchestrator(
        ['{"tool": "save_note", "arguments": {"content": "dedupe me"}}', "Done"],
        tmp_path,
    )
    orch.turn("remember: dedupe me")
    orch.turn("remember: dedupe me")
    assert repo.count() == 1


def test_empty_user_message(tmp_path):
    orch, _ = make_orchestrator(["ok"], tmp_path)
    turn = orch.turn("   ")
    assert turn.ok is True
    assert turn.text
