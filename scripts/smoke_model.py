"""Quick smoke test of the real model: load, one ordinary reply, one tool-call reply."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.llm.llama_cpp_provider import LlamaCppProvider  # noqa: E402
from app.orchestrator import extract_tool_call  # noqa: E402

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
provider = LlamaCppProvider(model_path, n_ctx=2048, n_threads=8, max_tokens=256, temperature=0.3)
print("model exists:", provider.is_available())

t0 = time.perf_counter()
sys_prompt = (
    "You are a helpful assistant. Keep answers under 60 words. "
    "To save a note, respond with ONLY this JSON line: "
    '{"tool": "save_note", "arguments": {"content": "..."}}'
)

print("\n--- ordinary ---")
start = time.perf_counter()
reply = provider.generate([
    {"role": "system", "content": sys_prompt},
    {"role": "user", "content": "Hi, quick check: is this laptop running locally?"},
])
print("reply:", reply)
print(f"gen time: {time.perf_counter()-start:.1f}s")

print("\n--- tool call ---")
start = time.perf_counter()
tool = provider.generate([
    {"role": "system", "content": sys_prompt},
    {"role": "user", "content": "Save a note: my project is called Vamsi Companion."},
])
print("raw:", tool)
parsed = extract_tool_call(tool)
print("parsed:", parsed)
print(f"gen time: {time.perf_counter()-start:.1f}s")

print(f"\ntotal wall (incl load): {time.perf_counter()-t0:.1f}s")