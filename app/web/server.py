"""Local HTTP server for the browser interface.

Binds to 127.0.0.1 only. Serves the static UI and three JSON endpoints:
- POST /api/chat
- GET  /api/notes
- GET  /api/health
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from app.llm.base import ModelOutputError, ModelTimeout, ModelUnavailable
from app.orchestrator import AssistantTurn, ConversationOrchestrator
from app.phone_actions import parse_phone_action
from app.storage.notes import NotesRepository
from app.stt import TranscriptionInputError, TranscriptionUnavailable, VoskTranscriber

log = logging.getLogger("vamsi.server")

_STATIC_DIR = Path(__file__).resolve().parent / "static"

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "VamsiCompanion/0.1"

    # ---- wiring set by the server ----
    orchestrator: ConversationOrchestrator
    notes: NotesRepository
    processed_lock: threading.Lock
    processed: dict
    cache_processed: bool
    phone_access_enabled: bool
    pairing_token: Optional[str]
    allow_local_without_token: bool
    transcriber: Optional[VoskTranscriber]

    def log_message(self, fmt, *args):  # quiet default logging noise
        log.debug(fmt, *args)

    # -- helpers -----------------------------------------------------------
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _client_is_loopback(self) -> bool:
        host = self.client_address[0]
        return host in ("127.0.0.1", "::1", "localhost")

    def _paired(self) -> bool:
        if not self.phone_access_enabled:
            return True
        if self.allow_local_without_token and self._client_is_loopback():
            return True
        token = self.headers.get("X-Vamsi-Pairing-Token", "")
        return bool(self.pairing_token) and secrets.compare_digest(token, self.pairing_token)

    def _require_pairing(self) -> bool:
        if self._paired():
            return True
        self._send_json(401, {
            "ok": False,
            "error": "Phone pairing required. Open the pairing URL printed by scripts\\start_phone.ps1.",
        })
        return False

    def _send_static(self, path: str) -> None:
        rel = path.lstrip("/")
        if rel == "" or rel == "index.html":
            rel = "index.html"
        safe = (_STATIC_DIR / rel).resolve()
        if not safe.is_relative_to(_STATIC_DIR) or not safe.is_file():
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        ext = safe.suffix.lower()
        self.send_response(200)
        self.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(safe.stat().st_size))
        self.end_headers()
        with safe.open("rb") as f:
            self.wfile.write(f.read())

    # -- routes ------------------------------------------------------------
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self._send_static("index.html")
            return
        if parsed.path.startswith("/static/"):
            self._send_static(parsed.path[len("/static/"):])
            return
        if parsed.path == "/api/notes":
            self._handle_list_notes(parsed.query)
            return
        if parsed.path == "/api/health":
            self._handle_health()
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            self._handle_chat()
            return
        if parsed.path == "/api/notes":
            self._handle_create_note()
            return
        if parsed.path == "/api/transcribe":
            self._handle_transcribe()
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/notes/"):
            self._handle_update_note(parsed.path.rsplit("/", 1)[-1])
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/notes/"):
            self._handle_delete_note(parsed.path.rsplit("/", 1)[-1])
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    # -- endpoint implementations -----------------------------------------
    def _read_json(self) -> dict:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 16384:
            raise ValueError("request body must be between 1 and 16384 bytes")
        self.connection.settimeout(15)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _handle_chat(self) -> None:
        if not self._require_pairing():
            return
        try:
            payload = self._read_json()
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip() or len(message) > 4000:
                raise ValueError("message must be a nonempty string up to 4000 characters")
            cid = payload.get("conversation_id")
            rid = payload.get("request_id")
            for value in (cid, rid):
                if value is not None and (not isinstance(value, str) or not 0 < len(value) <= 128):
                    raise ValueError("IDs must be nonempty strings up to 128 characters")
        except (ValueError, UnicodeError, OSError) as exc:
            self.close_connection = True
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        # Serialize the whole request, including cache lookup and database commit.
        with self.processed_lock:
            fingerprint = json.dumps([cid, message])
            cached = self.processed.get(rid) if rid and self.cache_processed else None
            if cached:
                if cached[0] != fingerprint:
                    self._send_json(409, {"ok": False, "error": "request_id reused with different content"})
                else:
                    self._send_json(200, cached[1])
                return
            if cid:
                orch = self.sessions.get(cid)
                if orch is None:
                    self._send_json(409, {"ok": False, "error": "Conversation expired; start a new chat."})
                    return
            else:
                template = self.orchestrator
                orch = ConversationOrchestrator(template.provider, template.registry,
                    max_turns=template.max_turns, max_tool_iterations=template.max_tool_iterations,
                    request_timeout=template.request_timeout)
                self.sessions[orch.conversation_id] = orch
                while len(self.sessions) > 100:
                    self.sessions.pop(next(iter(self.sessions)))
            phone_action = parse_phone_action(message.strip())
            if phone_action is not None:
                response = AssistantTurn(
                    phone_action.reply,
                    conversation_id=orch.conversation_id,
                    tool_calls=[{"tool": "phone_action", "arguments": phone_action.action}],
                    seconds=0.0,
                    ok=True,
                ).to_dict()
                if phone_action.action.get("type") in {
                    "open_app",
                    "read_notifications",
                    "reply_notification",
                    "direct_whatsapp",
                    "list_whatsapp_apps",
                }:
                    response["actions"] = [phone_action.action]
            else:
                response = orch.turn(message.strip()).to_dict()
            if rid and self.cache_processed and response.get("ok"):
                self.processed[rid] = (fingerprint, response)
                while len(self.processed) > 1000:
                    self.processed.pop(next(iter(self.processed)))
            self._send_json(200, response)

    def _handle_list_notes(self, query_string: str) -> None:
        if not self._require_pairing():
            return
        q = parse_qs(query_string).get("q", [""])[0]
        try:
            notes = self.notes.find(q) if q else self.notes.all(limit=100)
            self._send_json(200, {"ok": True, "count": len(notes),
                                  "notes": [n.to_dict() for n in notes]})
        except Exception as exc:  # noqa: BLE001
            log.exception("notes list failed")
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_create_note(self) -> None:
        if not self._require_pairing():
            return
        try:
            payload = self._read_json()
            content = payload.get("content")
            title = payload.get("title", "")
            if not isinstance(content, str) or not content.strip() or len(content) > 4000:
                raise ValueError("content must be a nonempty string up to 4000 characters")
            if not isinstance(title, str) or len(title) > 200:
                raise ValueError("title must be a string up to 200 characters")
            saved = self.notes.save(title, content)
            self._send_json(200, {"ok": True, **saved})
        except (ValueError, UnicodeError, OSError) as exc:
            self.close_connection = True
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            log.exception("note create failed")
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_update_note(self, note_id: str) -> None:
        if not self._require_pairing():
            return
        try:
            if not note_id or len(note_id) > 64:
                raise ValueError("note id is invalid")
            payload = self._read_json()
            title = payload.get("title") if "title" in payload else None
            content = payload.get("content") if "content" in payload else None
            if title is not None and (not isinstance(title, str) or len(title) > 200):
                raise ValueError("title must be a string up to 200 characters")
            if content is not None and (not isinstance(content, str) or not content.strip() or len(content) > 4000):
                raise ValueError("content must be a nonempty string up to 4000 characters")
            note = self.notes.update(note_id, title=title, content=content)
            self._send_json(200, {"ok": True, "note": note.to_dict()})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            status = 404 if "not found" in str(exc).lower() else 500
            self._send_json(status, {"ok": False, "error": str(exc)})

    def _handle_delete_note(self, note_id: str) -> None:
        if not self._require_pairing():
            return
        try:
            if not note_id or len(note_id) > 64:
                raise ValueError("note id is invalid")
            deleted = self.notes.delete(note_id)
            if not deleted:
                self._send_json(404, {"ok": False, "error": "note not found"})
                return
            self._send_json(200, {"ok": True, "deleted": True, "note_id": note_id})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_transcribe(self) -> None:
        if not self._require_pairing():
            return
        try:
            content_type = self.headers.get_content_type()
            if content_type not in {"audio/wav", "audio/wave", "audio/x-wav"}:
                raise TranscriptionInputError("Voice upload must be WAV audio.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 44 < length <= 5_000_000:
                raise TranscriptionInputError("Voice audio must be between 44 bytes and 5 MB.")
            if self.transcriber is None:
                raise TranscriptionUnavailable("Voice transcription is not configured on the backend.")
            self.connection.settimeout(30)
            audio = self.rfile.read(length)
            text = self.transcriber.transcribe_wav_bytes(audio)
            self._send_json(200, {"ok": True, "text": text})
        except TranscriptionInputError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except TranscriptionUnavailable as exc:
            self._send_json(503, {"ok": False, "error": str(exc)})
        except (ValueError, UnicodeError, OSError) as exc:
            self.close_connection = True
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            log.exception("voice transcription failed")
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_health(self) -> None:
        self._send_json(200, {
            "ok": True,
            "provider": self.orchestrator.provider.name,
            "model_available": self.orchestrator.provider.is_available(),
            "voice_transcription_available": bool(self.transcriber and self.transcriber.is_available()),
            "phone_access_enabled": self.phone_access_enabled,
            "paired": self._paired(),
        })


class AppServer:
    def __init__(
        self,
        orchestrator: ConversationOrchestrator,
        notes: NotesRepository,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        cache_processed: bool = True,
        phone_access_enabled: bool = False,
        pairing_token: Optional[str] = None,
        allow_local_without_token: bool = True,
        transcriber: Optional[VoskTranscriber] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.notes = notes
        self.host = host
        self.port = port
        self.cache_processed = cache_processed
        self.phone_access_enabled = phone_access_enabled
        self.pairing_token = pairing_token
        self.allow_local_without_token = allow_local_without_token
        self.transcriber = transcriber
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

        if host not in ("127.0.0.1", "localhost", "::1") and not phone_access_enabled:
            raise ValueError("Non-localhost binding requires PHONE_ACCESS_ENABLED=1")
        if phone_access_enabled and not pairing_token:
            raise ValueError("Phone access requires a pairing token")
        self._handler = type("AppHandler", (_Handler,), {
            "orchestrator": orchestrator, "notes": notes,
            "cache_processed": cache_processed, "processed_lock": threading.Lock(),
            "processed": {}, "sessions": {},
            "phone_access_enabled": phone_access_enabled,
            "pairing_token": pairing_token,
            "allow_local_without_token": allow_local_without_token,
            "transcriber": transcriber})

    def start(self) -> None:
        if self._httpd is None:
            self._httpd = ThreadingHTTPServer((self.host, self.port), self._handler)
            self.port = self._httpd.server_address[1]

    def serve_forever(self) -> None:
        self._httpd.serve_forever()  # type: ignore[union-attr]

    def run_in_thread(self) -> None:
        self.start()
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            if self._thread and self._thread.is_alive():
                self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
