"""Storage: save, retrieve, search, persistence, duplicate handling."""

from app.storage.notes import NotesRepository


def test_save_and_get(notes_repo):
    result = notes_repo.save("Projects", "my project is called Vamsi Companion")
    assert result["note"]["id"]
    assert result["duplicate"] is False

    loaded = notes_repo.get(result["note"]["id"])
    assert loaded is not None
    assert loaded.title == "Projects"
    assert "Vamsi Companion" in loaded.content
    assert loaded.created_at


def test_count_after_save(notes_repo):
    notes_repo.save("A", "first note")
    notes_repo.save("B", "second note")
    assert notes_repo.count() == 2


def test_duplicate_save_returns_existing(notes_repo):
    first = notes_repo.save("T", "same content")
    second = notes_repo.save("T", "same content")
    assert second["duplicate"] is True
    assert second["note"]["id"] == first["note"]["id"]
    assert notes_repo.count() == 1


def test_duplicate_different_title_is_distinct(notes_repo):
    """Two notes that differ only by title are separate saves (different requests)."""
    first = notes_repo.save("Title A", "identical body")
    second = notes_repo.save("Title B", "identical body")
    assert second["duplicate"] is False
    assert second["note"]["id"] != first["note"]["id"]
    assert notes_repo.count() == 2


def test_find_by_keyword(notes_repo):
    notes_repo.save("", "a note about llamas and alpacas")
    notes_repo.save("", "completely unrelated shopping list")
    results = notes_repo.find("llama")
    assert len(results) == 1
    assert "llamas" in results[0].content


def test_find_case_insensitive(notes_repo):
    notes_repo.save("", "My Project is called VAMS!" )
    results = notes_repo.find("project")
    assert len(results) == 1


def test_empty_query_returns_empty(notes_repo):
    notes_repo.save("", "some unrelated content")
    assert notes_repo.find("") == []
    assert notes_repo.find("   ") == []


def test_no_match_returns_empty(notes_repo):
    notes_repo.save("", "one note")
    assert notes_repo.find("nonexistent-term-xyz") == []


def test_persistence_across_reopen(repo_path):
    repo = NotesRepository(repo_path)
    repo.save("Note", "persistent value 12345")
    assert repo.count() == 1

    reopened = NotesRepository(repo_path)
    assert reopened.count() == 1
    found = reopened.find("persistent")
    assert len(found) == 1
    assert found[0].content == "persistent value 12345"
    assert found[0].id


def test_all_ordered_recent_first(notes_repo):
    notes_repo.save("", "old note")
    notes_repo.save("", "new note")
    all_notes = notes_repo.all()
    assert all_notes[0].content == "new note"


def test_update_note_content_and_title(notes_repo):
    saved = notes_repo.save("Old", "old memory")
    updated = notes_repo.update(saved["note"]["id"], title="New", content="new memory")
    assert updated.title == "New"
    assert updated.content == "new memory"
    assert updated.updated_at >= updated.created_at


def test_delete_note(notes_repo):
    saved = notes_repo.save("Delete", "remove me")
    assert notes_repo.delete(saved["note"]["id"]) is True
    assert notes_repo.get(saved["note"]["id"]) is None
    assert notes_repo.delete(saved["note"]["id"]) is False
