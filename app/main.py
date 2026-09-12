"""Application entry point: builds config, storage, tools, model, and server."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from app.config import Config
from app.orchestrator import ConversationOrchestrator
from app.storage.notes import NotesRepository
from app.tools.notes_tools import register_note_tools
from app.tools.registry import ToolRegistry
from app.web.server import AppServer


def build_app(config=None):
    config = config or Config()
    config.ensure_dirs()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    notes = NotesRepository(config.database_path)
    registry = ToolRegistry()
    register_note_tools(registry, notes)

    provider = None
    if config.model_available:
        from app.llm.llama_cpp_provider import LlamaCppProvider

        provider = LlamaCppProvider(
            config.model_path,
            n_ctx=config.n_ctx,
            n_threads=config.n_threads,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    else:
        from app.llm.mock_provider import MockProvider

        provider = MockProvider(available=False, reason="model file not found")

    orchestrator = ConversationOrchestrator(
        provider,
        registry,
        max_turns=config.max_turns,
        max_tool_iterations=config.max_tool_iterations,
        request_timeout=config.request_timeout_seconds,
    )
    server = AppServer(orchestrator, notes, host=config.host, port=config.port)
    return server, orchestrator, notes, registry, config, provider


def main() -> int:
    server, orchestrator, _notes, _registry, config, provider = build_app()
    print(f"VamsiCompanion starting on {server.url}")
    print(f"  model:  {config.model_path}")
    print(f"  data:   {config.database_path}")
    print(f"  status: {provider.name} available={provider.is_available()}")
    try:
        server.start()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.stop()
    finally:
        if hasattr(provider, "close"):
            provider.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())