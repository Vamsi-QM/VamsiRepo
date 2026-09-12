"""Conversation orchestration.

Responsibilities:
- Hold the system instruction and a bounded window of recent turns.
- Run the tool loop: request model -> parse a tool call if present ->
  validate + execute -> feed the structured result back -> repeat.
- Bound the loop with MAX_TOOL_ITERATIONS and a per-request timeout.
- Convert model/tool/storage failures into structured assistant answers so
  the UI never fabricates success.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from app.llm.base import ChatMessage, ModelOutputError, ModelProvider
from app.tools.registry import ToolRegistry
from app.tools.base import ToolCallError

log = logging.getLogger("vamsi.orchestrator")

_SYSTEM_PROMPT = """You are Vamsi, a helpful personal AI companion running locally on this laptop. You keep answers short and natural. You have a note store on this machine.

Only these two tools exist: save_note, find_notes. Never invent other tools, and never run commands, code, SQL, or file paths.

Examples of when to use a tool:
Example: User: "Save a note: my favorite color is blue." -> {"tool": "save_note", "arguments": {"content": "my favorite color is blue"}}
Example: User: "What is my project called?" -> {"tool": "find_notes", "arguments": {"query": "project"}}

Then, after the tool result, summarize it for the user.

HARD RULES:
- When the user asks you to save or remember something, your first output is the save_note tool call with the exact words from the user.
- When the user asks about anything you might have stored earlier (e.g. "what is my project called?", "do you remember X?", "what did I save about X?"), your first output is a find_notes tool call using keywords from the question.
- If a tool result says saved:true, THEN tell the user the note was saved. Never claim a note was saved, stored, or remembered before seeing that result.
- If find_notes returns count:0, tell the user you could not find a matching note.
- For any other message, reply in plain conversational text without JSON."""


class _BoundedContext:
    def __init__(self, max_turns: int) -> None:
        self.max_turns = max_turns
        self._messages: List[Dict[str, Any]] = []

    def add(self, role: str, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        self._messages.append(ChatMessage(role, content, tool_calls).to_dict())
        # Bound the non-system history.
        history = [m for m in self._messages if m["role"] != "system"]
        overflow = len(history) - max(self.max_turns * 2, 2)
        if overflow > 0:
            removed = 0
            keep: List[Dict[str, Any]] = []
            for message in self._messages:
                if message["role"] == "system":
                    keep.append(message)
                elif removed < overflow:
                    removed += 1
                else:
                    keep.append(message)
            self._messages = keep

    def messages(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in self._messages]

    def set_system(self, prompt: str) -> None:
        self._messages = [m for m in self._messages if m["role"] != "system"]
        self._messages.insert(0, ChatMessage("system", prompt).to_dict())

    def clear(self) -> None:
        system = [m for m in self._messages if m["role"] == "system"]
        self._messages = system


class AssistantTurn:
    def __init__(
        self,
        text: str,
        *,
        conversation_id: str,
        tool_calls: List[Dict[str, Any]] = None,
        seconds: float = 0.0,
        ok: bool = True,
        error: Optional[str] = None,
    ) -> None:
        self.text = text
        self.conversation_id = conversation_id
        self.tool_calls = tool_calls or []
        self.seconds = seconds
        self.ok = ok
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply": self.text,
            "conversation_id": self.conversation_id,
            "ok": self.ok,
            "error": self.error,
            "tool_calls": self.tool_calls,
            "seconds": round(self.seconds, 2),
        }


_TOOLCALL_START = re.compile(r'"(?:tool|name)"\s*:')

def _decode_json_strict(text: str) -> Dict[str, Any]:
    """Parse a JSON object, tolerating Qwen's double-brace template escaping."""
    candidates = [text, text.strip()[1:-1] if text.strip().startswith("{{") and text.strip().endswith("}}}") else text]
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ModelOutputError(f"malformed tool call JSON: {text[:120]!r}")


def _parse_openai_style(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert an OpenAI-style function object into our {'tool','arguments'} shape."""
    if isinstance(parsed.get("tool"), str):
        return parsed
    if isinstance(parsed.get("name"), str) or isinstance(parsed.get("function"), dict):
        args = parsed.get("arguments")
        if isinstance(parsed.get("function"), dict):
            name = parsed["function"].get("name")
            func_args = parsed["function"].get("arguments")
            if isinstance(name, str):
                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except json.JSONDecodeError:
                        raise ModelOutputError("tool call arguments are invalid JSON") from None
                return {"tool": name, "arguments": func_args if isinstance(func_args, dict) else {}}
        if isinstance(parsed.get("name"), str):
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    raise ModelOutputError("tool call arguments are invalid JSON") from None
            return {"tool": parsed["name"], "arguments": args if isinstance(args, dict) else {}}
    return None


def _extract_brace_block(text: str, start: int) -> str:
    """Return text from the first '{' at/after `start` through the matching final '}'."""
    brace = text.find("{", start)
    if brace == -1:
        return ""
    depth = 0
    in_str = False
    esc = False
    for i in range(brace, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace:i + 1]
        elif ch == "\n":
            # An unbalanced newline before closing suggests dialogue text,
            # stop early rather than swallowing the rest of the message.
            if depth <= 1:
                break
    return text[brace:brace + 1]


def extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Parse a tool call from assistant text. Returns None if none found.

    Handles three shapes:
      - Qwen native: <tool_call>{{"name": "...", "arguments": {...}}}</tool_call>
      - Protocol:    {"tool": "save_note", "arguments": {...}}
      - OpenAI:      {"name": "...", "arguments": {...}}

    Raises ModelOutputError if a tool-call marker is present but unparseable.
    """
    stripped = text.strip()
    if not stripped:
        raise ModelOutputError("empty assistant output")

    # 1) Explicit <tool_call>...</tool_call> blocks (Qwen native format).
    for block in re.findall(r"<tool_call>(.*?)</tool_call>", stripped, re.DOTALL):
        parsed = _decode_json_strict(block)
        converted = _parse_openai_style(parsed)
        if converted:
            return converted
        raise ModelOutputError(f"malformed <tool_call> content: {block[:120]!r}")

    # 2) A standalone JSON object whose first level holds a tool/name key.
    for match in _TOOLCALL_START.finditer(stripped):
        start = stripped.rfind("{", 0, match.start())
        if start == -1 or match.start() - start > 128:
            continue
        candidate = _extract_brace_block(stripped, start)
        if not candidate or candidate == "{":
            # The '{' opened but the object never closed: an attempted
            # tool call was truncated mid-JSON. Surface it so the loop can
            # ask the model to retry rather than silently ignoring the intent.
            prefix = stripped[start:match.end() + 8]
            if re.match(r'^\{"(tool|name|function)"', prefix):
                raise ModelOutputError(
                    f"truncated tool call JSON: {prefix!r}"
                )
            continue
        try:
            parsed = _decode_json_strict(candidate)
        except ModelOutputError:
            # Might be dialogue mentioning a tool; only treat as fatal when
            # the object clearly starts our protocol key.
            prefix = stripped[start:match.end() + 8]
            if re.match(r'^\{"(tool|name|function)"\s*:', prefix):
                raise
            continue
        if parsed is not None:
            converted = _parse_openai_style(parsed)
            if converted:
                return converted
    return None


class ConversationOrchestrator:
    def __init__(
        self,
        provider: ModelProvider,
        registry: ToolRegistry,
        *,
        max_turns: int = 12,
        max_tool_iterations: int = 4,
        request_timeout: float = 180.0,
        system_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.max_turns = max_turns
        self.max_tool_iterations = max_tool_iterations
        self.request_timeout = request_timeout
        self.conversation_id = conversation_id or uuid.uuid4().hex[:12]
        self._context = _BoundedContext(max_turns)
        self._context.set_system(system_prompt or _SYSTEM_PROMPT)

    def _tool_definitions(self) -> List[Dict[str, Any]]:
        """OpenAI-style function definitions for native tool calling."""
        definitions = []
        for schema in self.registry.schemas():
            props = {}
            required = []
            for arg, spec in (schema.get("parameters") or {}).items():
                arg_type = spec.get("type", "string")
                type_map = {"string": "string", "integer": "integer", "boolean": "boolean"}
                props[arg] = {"type": type_map.get(arg_type, "string")}
                if spec.get("description"):
                    props[arg]["description"] = spec["description"]
                if spec.get("required"):
                    required.append(arg)
            definitions.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema.get("description", ""),
                    "parameters": {"type": "object", "properties": props, "required": required},
                },
            })
        return definitions

    def turn(self, user_text: str) -> AssistantTurn:
        from app.note_policy import explicit_note_call, render_result
        started = time.perf_counter()
        user_text = (user_text or "").strip()
        trace = []
        def finish(text, ok=True, error=None):
            self._context.add("assistant", text)
            return AssistantTurn(text, conversation_id=self.conversation_id,
                                 tool_calls=trace, seconds=time.perf_counter()-started,
                                 ok=ok, error=error)
        if not user_text:
            return finish("Please enter a message.")
        self._context.add("user", user_text)
        try:
            call = explicit_note_call(user_text)
            if call is None:
                raw = self.provider.generate(self._context.messages(),
                    timeout=self.request_timeout, tools=self._tool_definitions())
                call = extract_tool_call(raw)
                if call is None:
                    # No tool ran: never present apparent storage confirmation.
                    if re.search(r"\b(saved|stored|remembered|noted|recorded)\b|remember (?:that|this|it)|made a note", raw, re.I):
                        return finish("No note was saved in this turn. To save one, say 'Save a note: ...'.")
                    return finish(raw.strip())
                if call.get("tool") == "save_note":
                    # Small models must not silently persist casual conversation.
                    return finish("To save that, say 'Save a note: ' followed by the exact text.",
                                  False, "Explicit save command required")
            name, args = call.get("tool", ""), call.get("arguments", {})
            result = self.registry.execute(name, args)
            trace.append({"tool": name, "arguments": args})
            # Tool replies come from committed storage, never a model paraphrase.
            return finish(render_result(result), result.get("ok", False), result.get("error"))
        except Exception as exc:
            log.warning("turn failed: %s", type(exc).__name__)
            return finish("I hit a problem: " + str(exc), False, str(exc))
