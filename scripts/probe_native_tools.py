"""Probe native llama-cpp-python tools= support with Qwen2.5."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llama_cpp import Llama  # noqa: E402

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
llm = Llama(model_path=str(model_path), n_ctx=2048, n_threads=8, verbose=False)

tools = [
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a note to permanent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "optional title"},
                    "content": {"type": "string", "description": "note text"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_notes",
            "description": "Search saved notes by keywords.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "keywords"}},
                "required": ["query"],
            },
        },
    },
]

SYSTEM = (
    "You are a helpful personal AI companion. You have the tools save_note and find_notes. "
    "When the user asks to save a note or to find saved notes, call the appropriate tool. "
    "For other questions reply normally and concisely."
)

cases = [
    ("save", "Save a note: my project is called Vamsi Companion."),
    ("greet", "Hi there, how are you?"),
    ("find_empty", "Do you remember anything about llamas?"),
    ("find", "What is my project called?"),
]

for label, user in cases:
    print(f"\n===== {label}: {user!r} =====")
    t0 = time.perf_counter()
    try:
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            tools=tools,
            temperature=0.2,
            max_tokens=256,
        )
        msg = out["choices"][0]["message"]
        print("content:", (msg.get("content") or "")[:200])
        print("tool_calls:", json.dumps(msg.get("tool_calls"), ensure_ascii=False))
        print(f"finish: {out['choices'][0].get('finish_reason')}")
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc)
    print(f"time: {time.perf_counter()-t0:.1f}s")