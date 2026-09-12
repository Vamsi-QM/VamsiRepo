"""End-to-end probe: drive the REAL model through the actual orchestrator.

Runs the full save -> find -> plain-chat sequence against a scratch DB so we
can verify the native-tool loop works before accepting via run_e2e.py.
"""

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.llm.llama_cpp_provider import LlamaCppProvider          # noqa: E402
from app.orchestrator import ConversationOrchestrator            # noqa: E402
from app.storage.notes import NotesRepository                    # noqa: E402
from app.tools.notes_tools import register_note_tools            # noqa: E402
from app.tools.registry import ToolRegistry                      # noqa: E402

SCRATCH = ROOT / "cache" / "probe_orch"
if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True)

model_path = ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
repo = NotesRepository(SCRATCH / "probe.db")
registry = ToolRegistry()
register_note_tools(registry, repo)
provider = LlamaCppProvider(model_path, n_ctx=2048, n_threads=8)
orch = ConversationOrchestrator(provider, registry, max_tool_iterations=4, request_timeout=120)

steps = [
    ("SAVE", "Save a note: my project is called Vamsi Companion."),
    ("FIND_IN_SAME_CONV", "What is my project called?"),
    ("PLAIN", "Hello there! How are you today?"),
]

failed = False
for label, text in steps:
    t0 = time.perf_counter()
    turn = orch.turn(text)
    dt = time.perf_counter() - t0
    print(f"\n===== {label} ({dt:.1f}s) =====")
    print(f"  ok:            {turn.ok}")
    print(f"  tool_calls:    {turn.tool_calls}")
    print(f"  text:          {turn.text[:300]!r}")
    if turn.error:
        print(f"  error:         {turn.error}")
    if label == "SAVE":
        nrows = repo.count()
        ok = turn.ok and len(turn.tool_calls) == 1 and turn.tool_calls[0]["tool"] == "save_note"
        print(f"  db rows:       {nrows}")
        failed = failed or not ok or nrows != 1
    elif label.startswith("FIND"):
        mentions = "vamsi" in turn.text.lower()
        ok = turn.ok and len(turn.tool_calls) == 1 and turn.tool_calls[0]["tool"] == "find_notes"
        print(f"  mentions name: {mentions}")
        print(f"  triggered tool: {ok}")
    elif label.startswith("PLAIN"):
        failed = failed or not turn.ok or bool(turn.tool_calls)

# FRESH conversation, mirroring the post-restart acceptance path.
print("\n===== FRESH CONVERSATION (post-restart path) =====")
orch2 = ConversationOrchestrator(provider, registry, max_tool_iterations=4, request_timeout=120)
t0 = time.perf_counter()
turn = orch2.turn("What is my project called?")
dt = time.perf_counter() - t0
print(f"  ({dt:.1f}s)")
print(f"  ok:            {turn.ok}")
print(f"  tool_calls:    {turn.tool_calls}")
print(f"  text:          {turn.text[:300]!r}")
mentions = "vamsi" in turn.text.lower()
fresh_ok = turn.ok and len(turn.tool_calls) == 1 and turn.tool_calls[0]["tool"] == "find_notes" and mentions
print(f"  mentions name: {mentions}")
failed = failed or not fresh_ok

print("\n===== DB CONTENTS =====")
for note in repo.all():
    print(f"  [{note.id}] {note.title!r}: {note.content!r}")

print(f"\nRESULT: {'PASS' if not failed else 'FAIL'}")
sys.exit(0 if not failed else 1)