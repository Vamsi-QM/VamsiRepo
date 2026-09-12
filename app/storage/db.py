"""SQLite storage layer for notes.

Uses parameterized queries everywhere. The database file lives under the
configured DATA_DIR (on D: by default).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at DESC);
"""


class DatabaseError(Exception):
    """Raised when a storage operation fails."""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error:
        pass
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:  # noqa: BLE001
        conn.rollback()
        raise DatabaseError(f"database operation failed: {exc}") from exc


def init_db(path: Optional[Path] = None) -> sqlite3.Connection:
    path = path or _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"could not initialize database at {path}: {exc}") from exc
    return conn


def _default_path() -> Path:
    try:
        from app.config import DEFAULT_CONFIG

        return DEFAULT_CONFIG.database_path
    except Exception:  # noqa: BLE001
        return Path("./companion.db")