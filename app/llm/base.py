"""Model provider interface. The conversation layer only talks to this.

A provider turns a chat message list into assistant text (possibly with a
tool-call request). `ModelUnavailable`, `ModelTimeout` and `ModelOutputError`
are the failure modes the orchestrator must handle without crashing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ModelUnavailable(Exception):
    """The model could not be loaded or the backend is not reachable."""


class ModelTimeout(Exception):
    """A single model request exceeded its time budget."""


class ModelOutputError(Exception):
    """The model produced unusable output (empty, malformed JSON, etc.)."""


class ChatMessage:
    def __init__(self, role: str, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        self.role = role  # one of system|user|assistant|tool
        self.content = content
        self.tool_calls = tool_calls or []

    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "content": self.content, "tool_calls": self.tool_calls}


class ModelProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        timeout: float = 180.0,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Return raw assistant text for the message list.

        `tools` (OpenAI-style function definitions) may be passed to enable
        native function calling; the provider is free to use or ignore it
        depending on backend capability.
        """