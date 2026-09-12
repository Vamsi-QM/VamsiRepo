"""Database failure handling: a failed write must not report success."""

import sqlite3
from pathlib import Path

import pytest

from app.storage.db import DatabaseError
from app.storage.notes import NotesRepository


class _ReadOnlyRepo(NotesRepository):
    """A repo whose connect function returns a read-only connection."""

    def __init__(self, db_path):
        super().__init__(db_path)

    def _conn(self):
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn


def test_save_failure_raises_not_false_success(tmp_path):
    path = tmp_path / "ro.db"
    # Initialize the schema on a writable connection first.
    writable = NotesRepository(path)
    writable.save("T", "seed content")
    repo = _ReadOnlyRepo(path)
    with pytest.raises(DatabaseError):
        repo.save("T", "this must fail")


def test_empty_content_rejected(tmp_path):
    repo = NotesRepository(tmp_path / "d.db")
    with pytest.raises(DatabaseError):
        repo.save("", "   ")


def test_corrupt_db_file_raises_clean_error(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a sqlite database at all")
    with pytest.raises(DatabaseError):
        NotesRepository(path)


def test_search_on_missing_table_does_not_crash_app_layer(tmp_path):
    """Deleting the table is a corrupted-state simulation; the repo must raise
    DatabaseError rather than lying about success."""
    repo = NotesRepository(tmp_path / "clean.db")
    repo.save("T", "exists")
    conn = sqlite3.connect(str(repo.db_path))
    conn.execute("DROP TABLE notes")
    conn.commit()
    conn.close()
    with pytest.raises(DatabaseError):
        repo.find("anything")