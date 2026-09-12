"""Note tools: save_note and find_notes."""

from __future__ import annotations

from typing import Any, Dict

from app.storage.notes import NotesRepository
from app.tools.base import Tool, ToolCallError


class SaveNoteTool(Tool):
    name = "save_note"
    description = "Save a note to permanent storage on this machine."
    parameters = {
        "title": {"type": "string", "required": False, "description": "Optional short title."},
        "content": {"type": "string", "required": True, "description": "The note text to store."},
    }

    def __init__(self, repo: NotesRepository) -> None:
        self.repo = repo

    def run(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        title = str(arguments.get("title") or "").strip()
        content = str(arguments.get("content") or "").strip()
        if not content:
            raise ToolCallError("save_note: content must not be empty")
        saved = self.repo.save(title, content)
        note = saved["note"]
        return {
            "saved": True,
            "duplicate": saved["duplicate"],
            "note_id": note["id"],
            "title": note["title"],
            "content": note["content"],
            "created_at": note["created_at"],
        }


class FindNotesTool(Tool):
    name = "find_notes"
    description = "Search saved notes by keywords and return matching notes."
    parameters = {
        "query": {"type": "string", "required": True, "description": "Keywords to search for."},
    }

    def __init__(self, repo: NotesRepository) -> None:
        self.repo = repo

    def run(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ToolCallError("find_notes: query must not be empty")
        notes = self.repo.find(query)
        return {
            "count": len(notes),
            "notes": [note.to_dict() for note in notes],
        }


def register_note_tools(registry, repo: NotesRepository) -> None:
    registry.register(SaveNoteTool(repo))
    registry.register(FindNotesTool(repo))