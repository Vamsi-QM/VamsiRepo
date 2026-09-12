"""Tool interfaces: a Tool produces structured results.

A tool declares its name, description, and a JSON-schema-like argument
specification. The caller (orchestrator) validates the name and arguments
before execution; tools never receive model-generated shell commands.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ToolCallError(Exception):
    """Raised for invalid tool names, missing arguments, or argument type errors."""


class Tool:
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}  # shape: {"arg": {"type": "string|integer|boolean", "required": bool}}

    @abstractmethod
    def run(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool. Return a plain dict result that is safe to log
        and to feed back to the model."""

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    @classmethod
    def validate_arguments(cls, arguments: Any) -> Dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ToolCallError(f"{cls.name}: arguments must be a JSON object")
        errors: List[str] = []
        for arg, spec in (cls.parameters or {}).items():
            present = arg in arguments and arguments[arg] is not None
            if spec.get("required") and not present:
                errors.append(f"missing required argument '{arg}'")
            elif present:
                expected = spec.get("type", "string")
                value = arguments[arg]
                if expected == "string" and not isinstance(value, str):
                    errors.append(f"argument '{arg}' must be a string, got {type(value).__name__}")
                elif expected == "integer":
                    if isinstance(value, bool) or not isinstance(value, int):
                        errors.append(f"argument '{arg}' must be an integer")
                elif expected == "boolean" and not isinstance(value, bool):
                    errors.append(f"argument '{arg}' must be a boolean")
        unknown = set(arguments) - set(cls.parameters)
        for arg in unknown:
            errors.append(f"unexpected argument '{arg}'")
        if errors:
            raise ToolCallError(f"{cls.name}: " + "; ".join(errors))
        return {k: v for k, v in arguments.items()}