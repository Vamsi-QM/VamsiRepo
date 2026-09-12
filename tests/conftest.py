"""Shared fixtures."""

import sys
from pathlib import Path

import pytest

from app.storage.notes import NotesRepository

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def notes_repo(tmp_path):
    return NotesRepository(tmp_path / "test.db")


@pytest.fixture()
def repo_path(tmp_path):
    return tmp_path / "notes.db"
@pytest.fixture()
def tmp_path():
    import uuid
    import shutil
    root = Path(__file__).resolve().parents[1] / "cache" / "test-runs" / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root)
