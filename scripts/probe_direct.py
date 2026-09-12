"""Probe: short system prompt + tool directive appended to the user message."""

import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llama_cpp import Llama  # noqa: E402

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
llm = Llama(model_path=str(model_path), n_ctx=2048, n_threads=8, verbose=False)

SYSTEM = (
    "You are Vamsi, a concise personal AI companion. "
    "You can save notes and search saved notes. Never invent tools. "
    "When the user asks to save or remember something, respond with ONLY one JSON line: "
    '{"tool": "save_note", "arguments": {"content": "..."}}\n'
    "When the user asks about previously saved information, respond with ONLY one JSON line: "
    '{"tool": "find_notes", "arguments": {"query": "..."}}\n'
    "Otherwise answer normally, no JSON."
)

DIRECTIVE = (
    "\n\nRespond with ONLY one of:\n"
    '- normal text, OR\n'
    '- {"tool": "save_note", "arguments": {"content": "..."}} if saving, OR\n'
    '- {"tool": "find_notes", "arguments": {"query": "..."}} if retrieving.\n'
    "Do not add surrounding words."
)

cases = [
    ("save", "Save a note: my project is called Vamsi Companion."),
    ("greet", "Hi there, how are you?"),
    ("find_empty", "What do you remember about llamas?"),
    ("find", "What is my project called?"),
    ("greet2", "Hello! Nice to meet you."),
]

for label, user in cases:
    print(f"\n===== {label} =====")
    t0 = time.perf_counter()
    out = llm.create_chat_completion(
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user + DIRECTIVE}],
        temperature=0.1, max_tokens=256,
    )
    c = (out["choices"][0]["message"].get("content") or "").strip()
    print("raw:", c[:160])
    if "<tool_call>" in c:
        print("  -> emitted native tool_call tag (need own parsing)")
    print(f"time: {time.perf_counter()-t0:.1f}s")