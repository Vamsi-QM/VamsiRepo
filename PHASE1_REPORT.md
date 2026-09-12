# Phase 1 independent review - 2026-09-12

Status: corrected implementation passes the scoped beginner acceptance flow.

## Original gaps found
- Claimed save honesty depended on model prompting; failed tools could be followed by false success prose.
- Existing E2E --db option did not configure DB_NAME and inspected the everyday database. Existing rows could falsely satisfy it.
- Shared orchestrator meant conversation IDs did not isolate histories.
- Concurrent duplicate requests could run before the cache was populated.
- ThreadPoolExecutor timeout waited during context-manager shutdown.
- Database error path leaked a connection.
- HTTP input shapes could crash handlers; arbitrary bind hosts were accepted.
- Dependencies were not pinned and setup did not check native-command exit codes.

## Corrections
- Explicit note-command routing, exact text saves, database-rendered success/errors/search results. Small-model chatter cannot override failed storage.
- Model-proposed writes require explicit save wording; note reads remain available as model tools.
- Separate bounded conversation contexts and New chat button; serialized request handling and conflict detection.
- Process-isolated inference with terminate-on-timeout, actual tokenizer-based history trimming, structured native tool output support.
- Connection cleanup, literal keyword search, bounded JSON requests, localhost binding.
- Dependency lock and setup error checks; no new model downloads.
- Isolated E2E test with unique random project name, actual real-model conversations, same-session retrieval, process restart, empty search, and an unchanged everyday database checksum.

## Verification evidence
67 automated tests passed (initial reviewed run: 9.80 seconds).
Real E2E PASS at cache\acceptance\b534427153af4610b001f81ff45b7044.
Unique note: Orchid-3b04472edc. Database row and returned note ID agreed.
Real model greeting: 12.25 seconds; model rainbow explanation after restart: 15.06 seconds.
Direct save and retrieval operations: approximately 0.02 seconds each.
Browser check on isolated test server: saved a browser-test note, clicked New chat, retrieved it using two keywords. All expected results were visibly present.
No everyday notes were removed or used as acceptance fixtures.

## Current architecture
Browser -> local HTTP server -> per-conversation orchestrator.
Explicit notes -> registered tools -> SQLite -> factual renderer.
Ordinary chat -> replaceable model provider -> persistent local inference subprocess.
The development-agent system and Android are not implemented in Phase 1.

## Important scope adjustment
This version deliberately uses deterministic English note-command routing to establish dependable storage. It does not claim that Qwen reliably interprets every possible memory request. General AI chat still uses the real model. Arbitrary language, semantic retrieval, perfectly reliable chat, and self-building are future work. No regex filter can guarantee honesty for every possible model sentence; only tool results are authoritative.

## Reproduce
cd D:\VamsiCompanion
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\run_e2e.py
.\scripts\start.ps1
Open http://127.0.0.1:8765.

Model: models\qwen2.5-1.5b-instruct-q4_k_m.gguf
Python: .uv_python; virtual environment: .venv
Dependencies: requirements.lock; caches: cache and .uv_cache
Everyday notes: data\companion.db
Test artifacts: cache\acceptance, cache\ui-review, cache\test-runs
Fresh setup was inspected and improved, not rerun from an empty environment.
