"""Local HTTP server for the browser interface.

Binds to 127.0.0.1 only. Serves the static UI and three JSON endpoints:
- POST /api/chat
- GET  /api/notes
- GET  /api/health
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from app.llm.base import ModelOutputError, ModelTimeout, ModelUnavailable
from app.orchestrator import ConversationOrchestrator
from app.storage.notes import NotesRepository

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
            response = orch.turn(message.strip()).to_dict()
            if rid and self.cache_processed and response.get("ok"):
                self.processed[rid] = (fingerprint, response)
                while len(self.processed) > 1000:
                    self.processed.pop(next(iter(self.processed)))
            self._send_json(200, response)

    def _handle_list_notes(self, query_string: str) -> None:
        q = parse_qs(query_string).get("q", [""])[0]
        try:
            notes = self.notes.find(q) if q else self.notes.all(limit=100)
            self._send_json(200, {"ok": True, "count": len(notes),
                                  "notes": [n.to_dict() for n in notes]})
        except Exception as exc:  # noqa: BLE001
            log.exception("notes list failed")
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_create_note(self) -> None:
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

    def _handle_health(self) -> None:
        self._send_json(200, {
            "ok": True,
            "provider": self.orchestrator.provider.name,
            "model_available": self.orchestrator.provider.is_available(),
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
    ) -> None:
        self.orchestrator = orchestrator
        self.notes = notes
        self.host = host
        self.port = port
        self.cache_processed = cache_processed
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Phase 1 must bind to localhost")
        self._handler = type("AppHandler", (_Handler,), {
            "orchestrator": orchestrator, "notes": notes,
            "cache_processed": cache_processed, "processed_lock": threading.Lock(),
            "processed": {}, "sessions": {}})

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
