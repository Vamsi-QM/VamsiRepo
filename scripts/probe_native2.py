"""Probe native tools= across all cases; dump exact content to understand format."""

import sys, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llama_cpp import Llama

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
llm = Llama(model_path=str(model_path), n_ctx=2048, n_threads=8, verbose=False)

tools = [
    {"type": "function", "function": {"name": "save_note", "description": "Save a note to permanent storage on this machine.",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["content"]}}},
    {"type": "function", "function": {"name": "find_notes", "description": "Search saved notes by keywords and return matches.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]

SYSTEM = ("You are Vamsi, a helpful personal AI companion running locally. "
          "You have the tools save_note and find_notes. Call a tool only when the user asks to "
          "save a note or to retrieve saved notes. Otherwise reply normally and concisely.")

cases = [
    ("save", "Save a note: my project is called Vamsi Companion."),
    ("greet", "Hi there, how are you?"),
    ("find_empty", "What do you remember about llamas?"),
    ("find", "What is my project called?"),
]

for label, user in cases:
    print(f"\n===== {label} =====")
    t0 = time.perf_counter()
    out = llm.create_chat_completion(
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        tools=tools, temperature=0.1, max_tokens=256,
    )
    msg = out["choices"][0]["message"]
    content = msg.get("content") or ""
    print("content bytes:", repr(content[:250]))
    print("tool_calls:", json.dumps(msg.get("tool_calls"), ensure_ascii=False))
    print(f"time: {time.perf_counter()-t0:.1f}s")