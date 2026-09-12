"""Tool registry: the only way tools are exposed to the model."""

from __future__ import annotations

from typing import Any, Dict, List

from app.tools.base import Tool, ToolCallError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool must have a name")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolCallError(f"unknown tool '{name}'")
        return tool

    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> List[Dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def validate(self, name: str, arguments: Any) -> Dict[str, Any]:
        """Validate a proposed tool call without executing it."""
        tool = self.get(name)
        return tool.validate_arguments(arguments)

    def execute(self, name: str, arguments: Any) -> Dict[str, Any]:
        """Validate and execute a tool call. Returns {'ok': bool, ...}."""
        try:
            tool = self.get(name)
        except ToolCallError as exc:
            return {"ok": False, "tool": name, "error": str(exc)}
        try:
            validated = tool.validate_arguments(arguments)
        except ToolCallError as exc:
            return {"ok": False, "tool": name, "error": str(exc)}
        try:
            result = tool.run(validated)
            return {"ok": True, "tool": name, "result": result}
        except ToolCallError as exc:
            return {"ok": False, "tool": name, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - tool boundary
            return {"ok": False, "tool": name, "error": f"{type(exc).__name__}: {exc}"}