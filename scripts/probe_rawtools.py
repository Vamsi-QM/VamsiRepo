"""Dump raw native-tools output fully."""

import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llama_cpp import Llama

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
llm = Llama(model_path=str(model_path), n_ctx=2048, n_threads=8, verbose=False)

tools = [{"type": "function", "function": {"name": "save_note", "description": "Save a note to permanent storage.",
   "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["content"]}}}]

out = llm.create_chat_completion(
    messages=[{"role": "system", "content": "You are a helpful assistant with tool save_note."},
              {"role": "user", "content": "Save a note: my project is called Vamsi Companion."}],
    tools=tools, temperature=0.2, max_tokens=128,
)
print(json.dumps(out, ensure_ascii=False, indent=2)[:3000])

# Also test without tools, forcing the inline format
print("\n--- NO tools param, generic ---")
out2 = llm.create_chat_completion(
    messages=[{"role": "system", "content": "Reply with ONLY one JSON line: {\"tool\": \"save_note\", \"arguments\": {\"content\": \"...\"}}"},
              {"role": "user", "content": "Save a note: my project is called Vamsi Companion."}],
    temperature=0.2, max_tokens=128,
)
c = out2["choices"][0]["message"].get("content") or ""
print(repr(c[:400]))