"""Deterministic boundaries for explicit note commands and factual tool replies."""
import re


def explicit_note_call(text):
    save = re.match(
        r"^(?:save\s+(?:a\s+)?note(?:\s*:|\s+that\s+|\s+saying\s+|\s+)|remember\s*:?\s+)(.+)$",
        text,
        re.I | re.S,
    )
    if save:
        return {"tool": "save_note", "arguments": {"content": save.group(1).strip()}}
    find = re.match(r"^(?:find|search)\s+(?:my\s+)?notes\s*:?\s+(.+)$", text, re.I | re.S)
    if find:
        return {"tool": "find_notes", "arguments": {"query": find.group(1).strip()}}
    if re.match(r"^(?:what|which|where|when|who|how)\b.*\bmy\b|^do you remember\b|^what did I (?:save|tell)", text, re.I):
        stop = set('what which where when who how is are was were my the a an called named do you remember did i save tell about please'.split())
        words = [w for w in re.findall(r"\w+", text.lower()) if w not in stop]
        if words:
            return {"tool": "find_notes", "arguments": {"query": " ".join(words)}}
    return None


def render_result(result):
    if not result.get("ok"):
        return "I couldn't complete that action: " + result.get("error", "tool failed")
    data = result["result"]
    if result["tool"] == "save_note":
        if not data.get("saved"):
            return "The note was not saved."
        return ('That note is already saved: ' if data.get('duplicate') else 'Saved note: ') + data['content']
    if result["tool"] == "find_notes":
        if not data.get("notes"):
            return "I couldn't find a matching saved note."
        return "Here's what I found in your saved notes:\n" + "\n".join(
            f"- {n['content']} [note {n['id']}]" for n in data['notes'][:10])
    return "Action completed."
