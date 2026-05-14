#!/usr/bin/env python3
"""MCP-facing tool helpers for MindTask."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core import MindTaskDB


class MindTaskMCPTools:
    """Small, JSON-friendly wrapper around MindTaskDB."""

    def __init__(self, config_path: Optional[str] = None):
        self.mindtask_db = MindTaskDB(config_path=config_path)

    def _ok(self, **payload: Any) -> Dict[str, Any]:
        return {"success": True, "timestamp": datetime.now().isoformat(), **payload}

    def _error(self, message: str) -> Dict[str, Any]:
        return {"success": False, "error": message, "timestamp": datetime.now().isoformat()}

    def list_projects(self) -> Dict[str, Any]:
        try:
            projects = self.mindtask_db.get_projects()
            return self._ok(data=projects, count=len(projects))
        except Exception as exc:
            return self._error(str(exc))

    def list_tasks(
        self,
        project_id: Optional[int] = None,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            tasks = self.mindtask_db.get_tasks(
                project_id=project_id,
                status=status,
                priority=priority,
                limit=limit or self.mindtask_db.config.default_task_limit,
            )
            return self._ok(
                data=tasks,
                count=len(tasks),
                filters={"project_id": project_id, "status": status, "priority": priority},
            )
        except Exception as exc:
            return self._error(str(exc))

    def get_task(self, task_id: int) -> Dict[str, Any]:
        try:
            task = self.mindtask_db.get_task(task_id)
            if not task:
                return self._error(f"Task {task_id} was not found")
            return self._ok(data=task)
        except Exception as exc:
            return self._error(str(exc))

    def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        project_id: Optional[int] = None,
        priority: int = 0,
        due_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            if not title.strip():
                return self._error("title is required")
            task_id = self.mindtask_db.create_task(
                title=title,
                description=description or "",
                project_id=project_id,
                priority=priority,
                due_date=due_date,
            )
            task = self.mindtask_db.get_task(task_id)
            return self._ok(data=task, task_id=task_id, message=f"Created task: {title}")
        except Exception as exc:
            return self._error(str(exc))

    def update_task(self, task_id: int, **kwargs: Any) -> Dict[str, Any]:
        try:
            success = self.mindtask_db.update_task(task_id, **kwargs)
            if not success:
                return self._error(f"Task {task_id} was not found or no supported fields were provided")
            return self._ok(data=self.mindtask_db.get_task(task_id), message=f"Updated task {task_id}")
        except Exception as exc:
            return self._error(str(exc))

    def complete_task(self, task_id: int) -> Dict[str, Any]:
        try:
            success = self.mindtask_db.complete_task(task_id)
            if not success:
                return self._error(f"Task {task_id} was not found")
            return self._ok(data=self.mindtask_db.get_task(task_id), message=f"Completed task {task_id}")
        except Exception as exc:
            return self._error(str(exc))

    def delete_task(self, task_id: int) -> Dict[str, Any]:
        try:
            success = self.mindtask_db.delete_task(task_id)
            if not success:
                return self._error(f"Task {task_id} was not found")
            return self._ok(message=f"Deleted task {task_id}")
        except Exception as exc:
            return self._error(str(exc))

    def get_stats(self) -> Dict[str, Any]:
        try:
            return self._ok(data=self.mindtask_db.get_stats())
        except Exception as exc:
            return self._error(str(exc))

    def search_tasks(self, keyword: str, limit: Optional[int] = None) -> Dict[str, Any]:
        try:
            if not keyword.strip():
                return self._error("keyword is required")
            results = self.mindtask_db.search_tasks(keyword, limit or self.mindtask_db.config.default_search_limit)
            return self._ok(data=results, count=len(results), keyword=keyword)
        except Exception as exc:
            return self._error(str(exc))

    def get_history(self, limit: int = 50, include_undone: bool = False) -> Dict[str, Any]:
        try:
            rows = self.mindtask_db.get_history(limit=limit, include_undone=include_undone)
            return self._ok(data=rows, count=len(rows))
        except Exception as exc:
            return self._error(str(exc))

    def undo_last_operation(self) -> Dict[str, Any]:
        try:
            history = self.mindtask_db.undo_last_operation()
            if not history:
                return self._error("No operation to undo")
            return self._ok(data=history, message=f"Undid history item {history['id']}")
        except Exception as exc:
            return self._error(str(exc))


def get_mcp_tool_schemas() -> List[Dict[str, Any]]:
    """Return JSON schemas for the available MindTask tools."""
    return [
        {
            "name": "MindTask_list_projects",
            "description": "List MindTask projects.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "MindTask_list_tasks",
            "description": "List tasks with optional filters.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "status": {"type": "integer", "enum": [0, 1, 2]},
                    "priority": {"type": "integer", "enum": [0, 1, 2, 3]},
                    "limit": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_get_task",
            "description": "Get one task by id.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_create_task",
            "description": "Create a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": "integer"},
                    "priority": {"type": "integer", "enum": [0, 1, 2, 3], "default": 0},
                    "due_date": {"type": "string"},
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_update_task",
            "description": "Update fields on a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": "integer"},
                    "priority": {"type": "integer", "enum": [0, 1, 2, 3]},
                    "status": {"type": "integer", "enum": [0, 1, 2]},
                    "due_date": {"type": ["string", "null"]},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_complete_task",
            "description": "Mark a task as done.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_delete_task",
            "description": "Delete a task.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_get_stats",
            "description": "Get task statistics.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "MindTask_search_tasks",
            "description": "Search tasks by keyword.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1},
                },
                "required": ["keyword"],
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_get_history",
            "description": "List operation history.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1},
                    "include_undone": {"type": "boolean", "default": False},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "MindTask_undo_last_operation",
            "description": "Undo the latest operation that has not already been undone.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]
