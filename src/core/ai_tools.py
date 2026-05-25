"""Controlled tool execution surface for MindTask AI actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

from .config import MindTaskConfig
from .database import MindTaskDB


READ_TOOLS = {
    "get_task",
    "get_tasks",
    "search_tasks",
    "get_projects",
    "get_project",
    "get_project_summaries",
    "get_stats",
    "get_history",
    "get_task_history",
}
WRITE_TOOLS = {
    "create_task",
    "update_task",
    "delete_task",
    "complete_task",
    "create_project",
    "update_project",
    "delete_empty_project",
}
WRITE_TOOL_RESULT_SUCCESS = {
    "create_task": "Task created successfully.",
    "update_task": "Task updated successfully.",
    "delete_task": "Task deleted successfully.",
    "complete_task": "Task completed successfully.",
    "create_project": "Project created successfully.",
    "update_project": "Project updated successfully.",
    "delete_empty_project": "Project deleted successfully.",
}
AI_SOURCE = "ai"


def openai_tool_definitions() -> list[Dict[str, Any]]:
    """Return OpenAI-compatible tool definitions for the MindTask action surface."""
    return [
        _tool_schema("get_task", "Read a task by ID.", {"task_id": _integer_schema()}),
        _tool_schema(
            "get_tasks",
            "List tasks with optional filters.",
            {
                "project_id": _nullable_integer_schema(),
                "status": _nullable_integer_schema(),
                "priority": _nullable_integer_schema(),
                "limit": _nullable_integer_schema(),
            },
            required=[],
        ),
        _tool_schema(
            "search_tasks",
            "Search tasks by title or description.",
            {"keyword": _string_schema(), "limit": _nullable_integer_schema()},
            required=["keyword"],
        ),
        _tool_schema("get_projects", "List projects.", {}),
        _tool_schema("get_project", "Read a project by ID.", {"project_id": _integer_schema()}),
        _tool_schema("get_project_summaries", "List projects with task counts.", {}),
        _tool_schema("get_stats", "Read task and project statistics.", {}),
        _tool_schema(
            "get_history",
            "Read operation history.",
            {"limit": _nullable_integer_schema(), "include_undone": _boolean_schema()},
            required=[],
        ),
        _tool_schema(
            "get_task_history",
            "Read operation history for one task.",
            {"task_id": _integer_schema(), "limit": _integer_schema(), "include_undone": _boolean_schema()},
            required=["task_id"],
        ),
        _tool_schema(
            "create_task",
            "Create a task.",
            {
                "title": _string_schema(),
                "description": _string_schema(),
                "project_id": _nullable_integer_schema(),
                "priority": _integer_schema(),
                "status": _integer_schema(),
                "due_date": _nullable_string_schema(),
                "due_mode": _string_schema(),
            },
            required=["title"],
        ),
        _tool_schema(
            "update_task",
            "Update a task.",
            {
                "task_id": _integer_schema(),
                "title": _string_schema(),
                "description": _string_schema(),
                "project_id": _nullable_integer_schema(),
                "priority": _integer_schema(),
                "status": _integer_schema(),
                "completed": _boolean_schema(),
                "due_date": _nullable_string_schema(),
                "due_mode": _string_schema(),
            },
            required=["task_id"],
        ),
        _tool_schema("delete_task", "Delete a task.", {"task_id": _integer_schema()}),
        _tool_schema("complete_task", "Mark a task completed.", {"task_id": _integer_schema()}),
        _tool_schema(
            "create_project",
            "Create a project.",
            {"name": _string_schema(), "description": _string_schema(), "color": _string_schema()},
            required=["name"],
        ),
        _tool_schema(
            "update_project",
            "Update a project.",
            {
                "project_id": _integer_schema(),
                "name": _string_schema(),
                "description": _string_schema(),
                "color": _string_schema(),
            },
            required=["project_id"],
        ),
        _tool_schema("delete_empty_project", "Delete a project only when it has no tasks.", {"project_id": _integer_schema()}),
    ]


@dataclass(frozen=True)
class ToolExecutionPolicy:
    allow_database_write: bool = False
    confirm_delete_actions: bool = True
    confirm_bulk_actions: bool = True

    @classmethod
    def from_config(cls, config: MindTaskConfig) -> "ToolExecutionPolicy":
        return cls(
            allow_database_write=config.ai_allow_database_write,
            confirm_delete_actions=config.ai_confirm_delete_actions,
            confirm_bulk_actions=config.ai_confirm_bulk_actions,
        )


class AIToolError(ValueError):
    """Raised when an AI tool request is invalid or unsupported."""


class AIToolExecutor:
    """Execute AI-requested actions through a strict whitelist."""

    def __init__(self, db: MindTaskDB, policy: Optional[ToolExecutionPolicy] = None):
        self.db = db
        self.policy = policy or ToolExecutionPolicy()

    def execute_action(
        self,
        action: Dict[str, Any],
        *,
        ai_batch_id: Optional[int] = None,
        approved: bool = False,
        high_risk_approved: bool = False,
    ) -> Dict[str, Any]:
        tool = self._action_tool(action)
        args = self._action_args(action)
        self._require_supported_tool(tool)

        approval_reason = self._approval_reason(tool, action, approved, high_risk_approved)
        if approval_reason:
            return {"status": "needs_approval", "tool": tool, "reason": approval_reason, "action": action}

        if tool in READ_TOOLS:
            return {"status": "ok", "tool": tool, "result": self._execute_read(tool, args)}
        if ai_batch_id is None:
            raise AIToolError("AI write actions require an operation batch.")
        return {"status": "ok", "tool": tool, "result": self._execute_write(tool, args, ai_batch_id)}

    def execute_actions(
        self,
        actions: Iterable[Dict[str, Any]],
        *,
        session_id: Optional[int] = None,
        user_message_id: Optional[int] = None,
        model: str = "",
        approved: bool = False,
        high_risk_approved: bool = False,
    ) -> Dict[str, Any]:
        action_list = list(actions)
        try:
            has_write = any(self._action_tool(action) in WRITE_TOOLS for action in action_list)
        except Exception as exc:
            return {
                "status": "error",
                "ai_batch_id": None,
                "results": [{"status": "error", "tool": "", "error": str(exc)}],
                "error": str(exc),
            }
        first_blocked = self._first_blocked_action(action_list, approved, high_risk_approved)
        if first_blocked is not None:
            return first_blocked

        if not has_write:
            results: list[Dict[str, Any]] = []
            for action in action_list:
                try:
                    results.append(
                        self.execute_action(action, approved=approved, high_risk_approved=high_risk_approved)
                    )
                except Exception as exc:
                    results.append(
                        {
                            "status": "error",
                            "tool": self._safe_action_tool(action),
                            "error": str(exc),
                        }
                    )
                    return {
                        "status": "error",
                        "ai_batch_id": None,
                        "results": results,
                        "error": str(exc),
                    }
            return {
                "status": "ok",
                "ai_batch_id": None,
                "results": results,
            }

        batch_id = self.db.create_ai_operation_batch(session_id=session_id, user_message_id=user_message_id, model=model)
        results: list[Dict[str, Any]] = []
        summary: list[Dict[str, Any]] = []
        try:
            for action in action_list:
                try:
                    result = self.execute_action(
                        action,
                        ai_batch_id=batch_id,
                        approved=approved,
                        high_risk_approved=high_risk_approved,
                    )
                    results.append(result)
                    if self._action_tool(action) in WRITE_TOOLS:
                        summary.append(
                            {
                                "tool": self._action_tool(action),
                                "arguments": self._action_args(action),
                                "result": result.get("result"),
                            }
                        )
                except Exception as exc:
                    error_result = {
                        "status": "error",
                        "tool": self._safe_action_tool(action),
                        "error": str(exc),
                    }
                    results.append(error_result)
                    summary.append(
                        {
                            "tool": self._safe_action_tool(action),
                            "arguments": self._safe_action_args(action),
                            "error": str(exc),
                        }
                    )
                    self.db.complete_ai_operation_batch(batch_id, summary, status="failed", error=str(exc))
                    return {
                        "status": "error",
                        "ai_batch_id": batch_id,
                        "results": results,
                        "error": str(exc),
                    }
        except Exception as exc:
            self.db.complete_ai_operation_batch(batch_id, summary, status="failed", error=str(exc))
            return {"status": "error", "ai_batch_id": batch_id, "results": results, "error": str(exc)}

        self.db.complete_ai_operation_batch(batch_id, summary)
        return {"status": "ok", "ai_batch_id": batch_id, "results": results}

    def _first_blocked_action(
        self,
        actions: list[Dict[str, Any]],
        approved: bool,
        high_risk_approved: bool,
    ) -> Optional[Dict[str, Any]]:
        if not self.policy.allow_database_write and not approved:
            return {"status": "needs_approval", "reason": "brave_mode_off", "actions": actions}
        write_count = sum(1 for action in actions if self._action_tool(action) in WRITE_TOOLS)
        if write_count > 1 and self.policy.confirm_bulk_actions and not high_risk_approved:
            return {"status": "needs_approval", "reason": "bulk_action", "actions": actions}
        for action in actions:
            tool = self._action_tool(action)
            if tool not in WRITE_TOOLS:
                continue
            reason = self._approval_reason(tool, action, approved, high_risk_approved)
            if reason:
                return {"status": "needs_approval", "tool": tool, "reason": reason, "action": action}
        return None

    def _approval_reason(self, tool: str, action: Dict[str, Any], approved: bool, high_risk_approved: bool) -> str:
        if not self.policy.allow_database_write and not approved:
            return "brave_mode_off"
        if tool in {"delete_task", "delete_empty_project"} and self.policy.confirm_delete_actions and not high_risk_approved:
            return "delete_action"
        return ""

    def _action_tool(self, action: Dict[str, Any]) -> str:
        if not isinstance(action, dict):
            raise AIToolError("AI action must be an object.")
        tool = action.get("tool") or action.get("type") or action.get("name")
        if not isinstance(tool, str) or not tool.strip():
            raise AIToolError("AI action is missing a tool name.")
        return tool.strip()

    def _safe_action_tool(self, action: Dict[str, Any]) -> str:
        try:
            return self._action_tool(action)
        except Exception:
            return ""

    def _action_args(self, action: Dict[str, Any]) -> Dict[str, Any]:
        args = action.get("arguments", action.get("args"))
        if args is None:
            return {key: value for key, value in action.items() if key not in {"tool", "type", "name"}}
        if not isinstance(args, dict):
            raise AIToolError("AI action arguments must be an object.")
        return dict(args)

    def _safe_action_args(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._action_args(action)
        except Exception:
            return {}

    def _require_supported_tool(self, tool: str) -> None:
        if tool not in READ_TOOLS and tool not in WRITE_TOOLS:
            raise AIToolError(f"Unsupported AI tool: {tool}")

    def _execute_read(self, tool: str, args: Dict[str, Any]) -> Any:
        handlers: Dict[str, Callable[..., Any]] = {
            "get_task": lambda **kwargs: self.db.get_task(int(kwargs["task_id"])),
            "get_tasks": self.db.get_tasks,
            "search_tasks": self.db.search_tasks,
            "get_projects": lambda **_kwargs: self.db.get_projects(),
            "get_project": lambda **kwargs: self.db.get_project(int(kwargs["project_id"])),
            "get_project_summaries": lambda **_kwargs: self.db.get_project_summaries(),
            "get_stats": lambda **_kwargs: self.db.get_stats(),
            "get_history": self.db.get_history,
            "get_task_history": self.db.get_task_history,
        }
        return handlers[tool](**args)

    def _execute_write(self, tool: str, args: Dict[str, Any], ai_batch_id: int) -> Any:
        if tool == "create_task":
            return self.db.create_task(source=AI_SOURCE, ai_batch_id=ai_batch_id, **args)
        if tool == "update_task":
            task_id = int(args.pop("task_id"))
            return self.db.update_task(task_id, source=AI_SOURCE, ai_batch_id=ai_batch_id, **args)
        if tool == "delete_task":
            return self.db.delete_task(int(args["task_id"]), source=AI_SOURCE, ai_batch_id=ai_batch_id)
        if tool == "complete_task":
            return self.db.complete_task(int(args["task_id"]), source=AI_SOURCE, ai_batch_id=ai_batch_id)
        if tool == "create_project":
            return self.db.create_project(source=AI_SOURCE, ai_batch_id=ai_batch_id, **args)
        if tool == "update_project":
            project_id = int(args.pop("project_id"))
            return self.db.update_project(project_id, source=AI_SOURCE, ai_batch_id=ai_batch_id, **args)
        if tool == "delete_empty_project":
            return self.db.delete_project(int(args["project_id"]), source=AI_SOURCE, ai_batch_id=ai_batch_id)
        raise AIToolError(f"Unsupported AI write tool: {tool}")


def _tool_schema(
    name: str,
    description: str,
    properties: Dict[str, Any],
    required: Optional[list[str]] = None,
) -> Dict[str, Any]:
    required_fields = required if required is not None else list(properties)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_fields,
                "additionalProperties": False,
            },
        },
    }


def _string_schema() -> Dict[str, str]:
    return {"type": "string"}


def _nullable_string_schema() -> Dict[str, Any]:
    return {"type": ["string", "null"]}


def _integer_schema() -> Dict[str, str]:
    return {"type": "integer"}


def _nullable_integer_schema() -> Dict[str, Any]:
    return {"type": ["integer", "null"]}


def _boolean_schema() -> Dict[str, str]:
    return {"type": "boolean"}
