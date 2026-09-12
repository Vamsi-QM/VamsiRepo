"""Notes repository backed by SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.storage.db import DatabaseError, connect, transaction


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _stable_id() -> str:
    return uuid.uuid4().hex[:16]


def _content_hash(title: str, content: str) -> str:
    return hashlib.sha256((title + "\x00" + content).encode("utf-8")).hexdigest()


class Note:
    def __init__(self, id: str, title: str, content: str, created_at: str, updated_at: str) -> None:
        self.id = id
        self.title = title
        self.content = content
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Note":
        return cls(row["id"], row["title"], row["content"], row["created_at"], row["updated_at"])


class NotesRepository:
    """Persists notes in SQLite. Uses one connection per operation so the
    repository is safe to share across server threads."""

    def __init__(self, db_path: Optional[Path] = None, connect_fn=None) -> None:
        self.db_path = db_path or Path("./companion.db")
        self._connect_fn = connect_fn or connect
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        return self._connect_fn(self.db_path)

    def _ensure_schema(self) -> None:
        from app.storage.db import _SCHEMA

        conn = self._conn()
        try:
            with transaction(conn):
                conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def save(self, title: str, content: str, *, content_fingerprint: Optional[str] = None) -> Dict[str, Any]:
        """Insert a note. Prevents exact-duplicate writes via the fingerprint;
        if an identical note already exists it is returned instead of re-inserted."""
        title = (title or "").strip()
        content = (content or "").strip()
        if not content:
            raise DatabaseError("cannot save a note with empty content")

        fingerprint = content_fingerprint or _content_hash(title, content)
        now = _utcnow()
        existing = self._find_by_fingerprint(fingerprint)
        if existing:
            return {"note": existing.to_dict(), "duplicate": True}

        note_id = _stable_id()
        conn = self._conn()
        try:
            with transaction(conn):
                conn.execute(
                    "INSERT INTO notes (id, title, content, fingerprint, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (note_id, title, content, fingerprint, now, now),
                )
        except sqlite3.IntegrityError as exc:
            conn.close()
            row = self._find_by_fingerprint(fingerprint)
            if row:
                return {"note": row.to_dict(), "duplicate": True}
            raise DatabaseError(f"could not save note: {exc}") from exc
        finally:
            conn.close()
        return {"note": {"id": note_id, "title": title, "content": content,
                          "created_at": now, "updated_at": now}, "duplicate": False}

    def _find_by_fingerprint(self, fingerprint: str) -> Optional[Note]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM notes WHERE fingerprint = ?", (fingerprint,)).fetchone()
            return Note.from_row(row) if row else None
        finally:
            conn.close()

    def find(self, query: str, limit: int = 50) -> List[Note]:
        """Keyword search over title and content. Parameterized LIKE query."""
        query = (query or "").strip()
        if not query:
            return []
        conn = self._conn()
        try:
            words = query.lower().split()[:12]
            clauses = ["(lower(title) LIKE ? ESCAPE '\\' OR lower(content) LIKE ? ESCAPE '\\')" for _ in words]
            patterns = []
            for word in words:
                escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                patterns.extend(["%" + escaped + "%"] * 2)
            sql = "SELECT * FROM notes WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC LIMIT ?"
            rows = conn.execute(sql, (*patterns, limit)).fetchall()
            return [Note.from_row(r) for r in rows]
        except sqlite3.Error as exc:
            raise DatabaseError(f"search failed: {exc}") from exc
        finally:
            conn.close()

    def get(self, note_id: str) -> Optional[Note]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            return Note.from_row(row) if row else None
        finally:
            conn.close()

    def update(self, note_id: str, *, title: Optional[str] = None, content: Optional[str] = None) -> Note:
        existing = self.get(note_id)
        if existing is None:
            raise DatabaseError("note not found")

        new_title = existing.title if title is None else title.strip()
        new_content = existing.content if content is None else content.strip()
        if not new_content:
            raise DatabaseError("cannot save a note with empty content")

        fingerprint = _content_hash(new_title, new_content)
        now = _utcnow()
        conn = self._conn()
        try:
            with transaction(conn):
                conn.execute(
                    "UPDATE notes SET title = ?, content = ?, fingerprint = ?, updated_at = ? WHERE id = ?",
                    (new_title, new_content, fingerprint, now, note_id),
                )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("another note already has that exact content") from exc
        finally:
            conn.close()

        updated = self.get(note_id)
        if updated is None:
            raise DatabaseError("note disappeared after update")
        return updated

    def delete(self, note_id: str) -> bool:
        conn = self._conn()
        try:
            with transaction(conn):
                cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cur.rowcount > 0
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._conn()
        try:
            return conn.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
        finally:
            conn.close()

    def all(self, limit: int = 100) -> List[Note]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM notes ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
            return [Note.from_row(r) for r in rows]
        finally:
            conn.close()
