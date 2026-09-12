"""Tool registry: validation and structured results."""

import pytest

from app.storage.notes import NotesRepository
from app.tools.base import Tool, ToolCallError
from app.tools.notes_tools import FindNotesTool, SaveNoteTool, register_note_tools
from app.tools.registry import ToolRegistry


@pytest.fixture()
def registry_with_notes(tmp_path):
    repo = NotesRepository(tmp_path / "t.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    return registry, repo


def test_registered_names(registry_with_notes):
    registry, _ = registry_with_notes
    assert registry.names() == ["find_notes", "save_note"]


def test_unknown_tool_raises(registry_with_notes):
    registry, _ = registry_with_notes
    with pytest.raises(ToolCallError):
        registry.validate("run_shell", {})
    result = registry.execute("run_shell", {})
    assert result["ok"] is False
    assert "unknown tool" in result["error"]


def test_save_note_requires_content(registry_with_notes):
    registry, _ = registry_with_notes
    with pytest.raises(ToolCallError):
        registry.validate("save_note", {})
    with pytest.raises(ToolCallError):
        registry.validate("save_note", {"content": 123})
    result = registry.execute("save_note", {})
    assert result["ok"] is False
    assert "content" in result["error"]


def test_save_note_strips_whitespace(registry_with_notes):
    registry, repo = registry_with_notes
    result = registry.execute("save_note", {"content": "   "})
    assert result["ok"] is False


def test_save_note_success(registry_with_notes):
    registry, _ = registry_with_notes
    result = registry.execute("save_note", {"title": "T", "content": "hello world"})
    assert result["ok"] is True
    assert result["result"]["saved"] is True
    assert result["result"]["note_id"]


def test_save_note_duplicate_result(registry_with_notes):
    registry, _ = registry_with_notes
    r1 = registry.execute("save_note", {"content": "dup content"})
    r2 = registry.execute("save_note", {"content": "dup content"})
    assert r1["ok"] is True and r2["ok"] is True
    assert r2["result"]["duplicate"] is True
    assert r2["result"]["note_id"] == r1["result"]["note_id"]


def test_find_notes_empty_query_rejected(registry_with_notes):
    registry, _ = registry_with_notes
    result = registry.execute("find_notes", {"query": ""})
    assert result["ok"] is False


def test_find_notes_no_results(registry_with_notes):
    registry, _ = registry_with_notes
    result = registry.execute("find_notes", {"query": "nothing-here"})
    assert result["ok"] is True
    assert result["result"]["count"] == 0
    assert result["result"]["notes"] == []


def test_find_notes_returns_saved(registry_with_notes):
    registry, _ = registry_with_notes
    registry.execute("save_note", {"content": "my project is called Vamsi Companion"})
    result = registry.execute("find_notes", {"query": "Vamsi"})
    assert result["ok"] is True
    assert result["result"]["count"] == 1
    assert "Vamsi Companion" in result["result"]["notes"][0]["content"]


def test_find_notes_search_asymmetric_values_preserved(registry_with_notes):
    registry, _ = registry_with_notes
    registry.execute("save_note", {"content": "alpha beta"})
    result = registry.execute("find_notes", {"query": "alpha beta"})
    assert result["result"]["count"] == 1


def test_custom_tool_registration_is_straightforward(tmp_path):
    """Adding a new tool requires subclassing Tool and registering it."""
    class PingTool(Tool):
        name = "ping"
        description = "pong"
        parameters = {}

        def run(self, arguments):
            return {"pong": True}

    repo = NotesRepository(tmp_path / "x.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    registry.register(PingTool())
    assert "ping" in registry.names()
    result = registry.execute("ping", {})
    assert result["ok"] is True
    assert result["result"]["pong"] is True


def test_non_dict_arguments_rejected(registry_with_notes):
    registry, _ = registry_with_notes
    result = registry.execute("save_note", ["not", "a", "dict"])
    assert result["ok"] is False