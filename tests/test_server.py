"""HTTP server tests with the mock provider, plus duplicate-request caching."""

import json
import urllib.error
import urllib.request

import pytest

from app.llm.base import ModelUnavailable
from app.llm.mock_provider import MockProvider
from app.orchestrator import ConversationOrchestrator
from app.storage.notes import NotesRepository
from app.tools.notes_tools import register_note_tools
from app.tools.registry import ToolRegistry
from app.web.server import AppServer


@pytest.fixture()
def server(tmp_path):
    repo = NotesRepository(tmp_path / "srv.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)

    class _Provider(MockProvider):
        name = "mock"

        def generate(self, messages, **kwargs):
            if not self.available:
                raise ModelUnavailable("mock provider unavailable")
            return super().generate(messages, **kwargs)

    provider = _Provider(available=True, replies=["Hi there!"])
    orch = ConversationOrchestrator(provider, registry)
    srv = AppServer(orch, repo, host="127.0.0.1", port=0, cache_processed=True)
    srv.start()
    srv.run_in_thread()
    yield srv, provider, repo
    srv.stop()


def _base(srv):
    return f"http://127.0.0.1:{srv._httpd.server_address[1]}"


def _post(srv, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(
        _base(srv) + "/api/chat", data=data,
        headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _json_request(srv, path, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {} if payload is None else {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(_base(srv) + path, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _raw_request(srv, path, method="POST", data=b"", headers=None):
    req = urllib.request.Request(_base(srv) + path, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_chat_endpoint_ok(server):
    srv, _, _ = server
    status, data = _post(srv, {"message": "hello"})
    assert status == 200
    assert data["ok"] is True
    assert data["reply"] == "Hi there!"




def test_chat_endpoint_returns_phone_open_action(server):
    srv, provider, _ = server
    status, data = _post(srv, {"message": "open YouTube"})

    assert status == 200
    assert data["ok"] is True
    assert data["reply"] == "Opening YouTube bro."
    assert data["actions"] == [{
        "type": "open_app",
        "app": "youtube",
        "label": "YouTube",
        "packages": ["com.google.android.youtube"],
        "intent": "launch",
    }]
    assert data["tool_calls"][0]["tool"] == "phone_action"
    assert provider._index == 0


def test_chat_endpoint_reports_unsupported_phone_app(server):
    srv, provider, _ = server
    status, data = _post(srv, {"message": "open calculator"})

    assert status == 200
    assert data["ok"] is True
    assert "I can open only these apps right now" in data["reply"]
    assert "actions" not in data
    assert data["tool_calls"][0]["arguments"] == {
        "type": "unsupported_open_app",
        "requested": "calculator",
    }
    assert provider._index == 0


def test_chat_endpoint_returns_notification_read_action(server):
    srv, provider, _ = server
    status, data = _post(srv, {"message": "read latest WhatsApp message"})

    assert status == 200
    assert data["ok"] is True
    assert data["reply"] == "Checking your WhatsApp notifications bro."
    assert data["actions"] == [{
        "type": "read_notifications",
        "app": "whatsapp",
        "label": "WhatsApp notifications",
        "limit": 5,
    }]
    assert data["tool_calls"][0]["tool"] == "phone_action"
    assert provider._index == 0

def test_chat_requires_message(server):
    srv, _, _ = server
    status, data = _post(srv, {"message": ""})
    assert status == 400
    assert data["ok"] is False


def test_health(server):
    srv, provider, _ = server
    with urllib.request.urlopen(_base(srv) + "/api/health", timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["ok"] is True
    assert data["provider"] == "mock"
    assert data["model_available"] is True


def test_notes_endpoint(server):
    srv, _, repo = server
    repo.save("T", "a memorable fact")
    with urllib.request.urlopen(_base(srv) + "/api/notes", timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["ok"] is True
    assert data["count"] == 1
    with urllib.request.urlopen(_base(srv) + "/api/notes?q=memorable", timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["count"] == 1


def test_notes_empty_search_empty_results(server):
    srv, _, repo = server
    repo.save("T", "something unrelated")
    with urllib.request.urlopen(_base(srv) + "/api/notes?q=zzzz", timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["count"] == 0


def test_notes_update_endpoint(server):
    srv, _, repo = server
    saved = repo.save("Old", "old memory")
    status, data = _json_request(
        srv,
        "/api/notes/" + saved["note"]["id"],
        method="PATCH",
        payload={"title": "New", "content": "new memory"},
    )
    assert status == 200
    assert data["ok"] is True
    assert data["note"]["title"] == "New"
    assert repo.get(saved["note"]["id"]).content == "new memory"


def test_notes_delete_endpoint(server):
    srv, _, repo = server
    saved = repo.save("Delete", "remove me")
    status, data = _json_request(srv, "/api/notes/" + saved["note"]["id"], method="DELETE")
    assert status == 200
    assert data["ok"] is True
    assert repo.get(saved["note"]["id"]) is None


def test_static_index_served(server):
    srv, _, _ = server
    with urllib.request.urlopen(_base(srv) + "/", timeout=30) as resp:
        body = resp.read().decode("utf-8")
    assert resp.status == 200
    assert "Vamsi Companion" in body


def test_model_unavailable_reported_honestly(server):
    srv, provider, _ = server
    provider.available = False
    status, data = _post(srv, {"message": "hello"})
    assert status == 200
    assert data["ok"] is False
    assert "unavailable" in data["error"].lower()
    assert "I hit a problem" in data["reply"] or "problem" in data["reply"].lower()


def test_duplicate_request_id_returns_cached(server):
    srv, _, _ = server
    rid = "same-request-abc"
    status, first = _post(srv, {"message": "ping", "request_id": rid})
    status2, second = _post(srv, {"message": "ping", "request_id": rid})
    assert status == 200 and status2 == 200
    assert first["reply"] == second["reply"]
    # Provider replied once; cached copy served second time.
    assert srv.orchestrator.provider._index == 1


def test_unknown_route_404(server):
    srv, _, _ = server
    try:
        with urllib.request.urlopen(_base(srv) + "/nope", timeout=30):
            pytest.fail("expected 404")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


def test_phone_mode_requires_pairing_token(tmp_path):
    repo = NotesRepository(tmp_path / "phone.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    provider = MockProvider(available=True, replies=["Hi phone!"])
    orch = ConversationOrchestrator(provider, registry)
    srv = AppServer(
        orch,
        repo,
        host="127.0.0.1",
        port=0,
        phone_access_enabled=True,
        pairing_token="secret-token",
        allow_local_without_token=False,
    )
    srv.start()
    srv.run_in_thread()
    try:
        status, data = _post(srv, {"message": "hello"})
        assert status == 401
        assert data["ok"] is False

        headers = {"X-Vamsi-Pairing-Token": "secret-token"}
        status, data = _post(srv, {"message": "hello"}, headers=headers)
        assert status == 200
        assert data["reply"] == "Hi phone!"
    finally:
        srv.stop()


def test_transcribe_requires_pairing_and_reports_missing_model(tmp_path):
    repo = NotesRepository(tmp_path / "voice.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    provider = MockProvider(available=True, replies=["ok"])
    orch = ConversationOrchestrator(provider, registry)
    from app.stt import VoskTranscriber

    srv = AppServer(
        orch,
        repo,
        host="127.0.0.1",
        port=0,
        phone_access_enabled=True,
        pairing_token="secret-token",
        allow_local_without_token=False,
        transcriber=VoskTranscriber(tmp_path / "missing-vosk-model"),
    )
    srv.start()
    srv.run_in_thread()
    try:
        wav_header_only = b"RIFF" + (b"\0" * 40)
        status, data = _raw_request(
            srv, "/api/transcribe", data=wav_header_only, headers={"Content-Type": "audio/wav"}
        )
        assert status == 401
        assert data["ok"] is False

        status, data = _raw_request(
            srv,
            "/api/transcribe",
            data=wav_header_only,
            headers={"Content-Type": "audio/wav", "X-Vamsi-Pairing-Token": "secret-token"},
        )
        assert status == 400
        assert data["ok"] is False
    finally:
        srv.stop()
