"""Deterministic fake provider for tests and for the no-model case.

When `available=False` it raises ModelUnavailable on generate, which is how
the app behaves when the model file is missing: it reports the failure rather
than pretending to work.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.llm.base import ModelOutputError, ModelProvider, ModelUnavailable


class MockProvider(ModelProvider):
    name = "mock"

    def __init__(self, replies: Optional[List[str]] = None, available: bool = True, reason: str = "") -> None:
        self._replies = list(replies or [])
        self._index = 0
        self.available = available
        self.reason = reason

    def is_available(self) -> bool:
        return self.available

    def generate(self, messages, **kwargs) -> str:
        if not self.available:
            raise ModelUnavailable(self.reason or "mock provider unavailable")
        if self._index < len(self._replies):
            reply = self._replies[self._index]
            self._index += 1
        else:
            reply = "Understood."
        if reply is None:
            raise ModelOutputError("mock provider returned empty output")
        return reply