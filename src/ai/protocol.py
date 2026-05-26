"""AI action protocol helpers.

MindTask prefers native OpenAI-compatible tool calls. For providers without
tool calling, the assistant may include exactly one JSON action block delimited
by the constants below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


ACTIONS_JSON_START = "<MINDTASK_ACTIONS_JSON>"
ACTIONS_JSON_END = "</MINDTASK_ACTIONS_JSON>"


@dataclass(frozen=True)
class AIAction:
    tool: str
    arguments: Dict[str, Any]
    tool_call_id: str = ""

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"tool": self.tool, "arguments": dict(self.arguments)}
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


class AIProtocolError(ValueError):
    """Raised when an AI action payload cannot be parsed safely."""


def extract_fallback_json(text: str) -> Optional[Any]:
    """Extract the fallback JSON payload between fixed action markers."""
    if ACTIONS_JSON_START not in text and ACTIONS_JSON_END not in text:
        return None
    start = text.find(ACTIONS_JSON_START)
    end = text.find(ACTIONS_JSON_END)
    if start < 0 or end < 0 or end <= start:
        raise AIProtocolError("AI action JSON markers are incomplete or out of order.")

    payload_start = start + len(ACTIONS_JSON_START)
    payload = text[payload_start:end].strip()
    if not payload:
        raise AIProtocolError("AI action JSON block is empty.")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AIProtocolError("AI action JSON block is invalid.") from exc


def actions_from_fallback_text(text: str) -> List[Dict[str, Any]]:
    """Return fallback actions from a fixed-marker JSON block.

    Natural language outside the markers is deliberately ignored.
    """
    payload = extract_fallback_json(text)
    if payload is None:
        return []
    return _actions_from_payload(payload)


def actions_from_openai_tool_calls(tool_calls: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Convert OpenAI-compatible tool calls into MindTask action dictionaries."""
    if not tool_calls:
        return []

    actions: List[Dict[str, Any]] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            raise AIProtocolError("Tool call must be an object.")
        function = call.get("function") or {}
        if not isinstance(function, dict):
            raise AIProtocolError("Tool call function must be an object.")
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise AIProtocolError("Tool call function name is missing.")
        raw_arguments = function.get("arguments") or "{}"
        if isinstance(raw_arguments, dict):
            arguments = raw_arguments
        elif isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments or "{}")
            except json.JSONDecodeError as exc:
                raise AIProtocolError("Tool call arguments must be valid JSON.") from exc
        else:
            raise AIProtocolError("Tool call arguments must be JSON text or an object.")
        if not isinstance(arguments, dict):
            raise AIProtocolError("Tool call arguments must be a JSON object.")
        actions.append(AIAction(name.strip(), arguments, str(call.get("id") or "")).as_dict())
    return actions


def actions_from_openai_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool actions from an OpenAI-compatible assistant message."""
    return actions_from_openai_tool_calls(message.get("tool_calls"))


def _actions_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and "actions" in payload:
        payload = payload["actions"]
    elif isinstance(payload, dict) and any(key in payload for key in ("tool", "type", "name")):
        payload = [payload]

    if not isinstance(payload, list):
        raise AIProtocolError("AI action payload must be an action object or action list.")

    actions: List[Dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise AIProtocolError("Each AI action must be an object.")
        tool = item.get("tool") or item.get("type") or item.get("name")
        if not isinstance(tool, str) or not tool.strip():
            raise AIProtocolError("Each AI action must include a tool name.")
        arguments = item.get("arguments", item.get("args"))
        if arguments is None:
            arguments = {key: value for key, value in item.items() if key not in {"tool", "type", "name"}}
        if not isinstance(arguments, dict):
            raise AIProtocolError("AI action arguments must be an object.")
        actions.append(AIAction(tool.strip(), arguments).as_dict())
    return actions
