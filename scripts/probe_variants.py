"""Test prompt variants for reliable find_notes triggering on retrieval questions."""

import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llama_cpp import Llama

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
llm = Llama(model_path=str(model_path), n_ctx=2048, n_threads=8, verbose=False)

TOOLS = [
    {"type": "function", "function": {"name": "save_note", "description": "Save a note to permanent storage on this machine.",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["content"]}}},
    {"type": "function", "function": {"name": "find_notes", "description": "Search saved notes by keywords and return matches.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]

variants = {
    "v1_retrieval_strong": (
        "You are a personal assistant on this laptop. You HAVE previously saved notes in a note store on this machine. "
        "To answer any question that could refer to previously saved information, you MUST call find_notes first. "
        "To save the content when the user says 'save a note: ...', you MUST call save_note. "
        "Tools you may call: save_note (title optional, content required), find_notes (query required). "
        "For general chit-chat, just reply naturally without tools."
    ),
    "v2_always_prefix": (
        "You are a personal AI companion running locally. You have exactly two tools:\n"
        "- save_note: must be called when the user tells you to save or remember something.\n"
        "- find_notes: must be called when the user asks about anything you might have stored earlier (e.g. 'what is my project called?', 'do you remember X?'). Search first, then answer only from the result.\n"
        "Never invent other tools. Reply to normal chat with plain text."
    ),
    "v3_2shot": (
        "You are a personal assistant with a note store. Use tools exactly when needed.\n"
        'Example: User: "Save a note: my favorite color is blue." -> {"tool": "save_note", "arguments": {"content": "my favorite color is blue"}}\n'
        'Example: User: "What is my project called?" -> {"tool": "find_notes", "arguments": {"query": "project"}}\n'
        'Then, after the tool result, summarize it for the user. Only these two tools exist: save_note, find_notes.'
    ),
}

case = ("find", "What is my project called?")
for vname, system in variants.items():
    print(f"\n===== {vname} =====")
    t0 = time.perf_counter()
    out = llm.create_chat_completion(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": case[1]}],
        tools=TOOLS, temperature=0.1, max_tokens=180,
    )
    msg = out["choices"][0]["message"]
    content = msg.get("content") or ""
    print("content:", repr(content[:180]))
    t1 = time.perf_counter()
    print(f"time: {t1-t0:.1f}s")