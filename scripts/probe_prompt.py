"""Probe the real orchestrator's exact prompt for the 3 acceptance scenarios."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.llm.llama_cpp_provider import LlamaCppProvider  # noqa: E402
from app.orchestrator import ConversationOrchestrator, extract_tool_call  # noqa: E402
from app.storage.notes import NotesRepository  # noqa: E402
from app.tools.notes_tools import register_note_tools  # noqa: E402
from app.tools.registry import ToolRegistry  # noqa: E402

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
provider = LlamaCppProvider(model_path, n_ctx=2048, n_threads=8, max_tokens=512, temperature=0.2)

for n, (label, msg) in enumerate([
    ("save", "Save a note: my project is called Vamsi Companion."),
    ("plain", "Hi, can you tell me what you're able to do?"),
    ("find", "What is my project called?"),
    ("plain2", "Hello! How are you doing today?"),
]):
    repo = NotesRepository(ROOT / "data" / f"probe_{n}.db")
    registry = ToolRegistry()
    register_note_tools(registry, repo)
    orch = ConversationOrchestrator(
        provider, registry, max_tool_iterations=2,
        system_prompt=(
            "You are a helpful personal AI companion running locally on this laptop. "
            "Keep replies short and natural. "
            "You have EXACTLY these two tools, and you must NEVER invent others: "
            '{"tool": "save_note", "arguments": {"title": "...", "content": "..."}} and '
            '{"tool": "find_notes", "arguments": {"query": "..."}}. '
            "Call a tool ONLY when the user asks to save a note or to retrieve/find saved notes. "
            "For any other question, reply normally in plain text without JSON."
        ),
    )
    print(f"\n===== {label}: {msg!r} =====")
    t0 = time.perf_counter()
    turn = orch.turn(msg)
    dt = time.perf_counter() - t0
    print("treply:", turn.text[:300])
    print("tools:", turn.tool_calls)
    print(f"time: {dt:.1f}s ok={turn.ok}")