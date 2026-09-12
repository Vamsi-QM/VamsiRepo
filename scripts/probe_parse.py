"""Probe the Qwen <tool_call> double-brace format and JSON parseability."""

import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

samples = [
    '<tool_call>\n{{"name": "find_notes", "arguments": {"query": "project"}}}</tool_call>',
    '<tool_call>{{"name": "save_note", "arguments": {"content": "my project is called Vamsi Companion.", "title": "Vamsi Companion Note"}}}</tool_call>',
    "{{'name': 'find_notes', 'arguments': {'query': 'project'}}}",
]

def parse_tool_call(text):
    m = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", text, re.DOTALL)
    inner = m.group(1).strip() if m else text.strip()
    for candidate in (inner, inner.replace("{{", "{").replace("}}", "}"), inner.replace("'", '"')):
        candidate = candidate.strip()
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("name"), str) and isinstance(obj.get("arguments"), dict):
            return {"tool": obj["name"], "arguments": obj["arguments"]}
    return None

for s in samples:
    print(repr(s), "->", parse_tool_call(s))