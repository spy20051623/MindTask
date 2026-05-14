#!/usr/bin/env python3
"""Core database access for MindTask."""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .config import load_config


def get_database_path(config_path: Optional[str] = None) -> str:
    """Return the configured SQLite database path."""
    return load_config(config_path).database_path


def get_schema_path(config_path: Optional[str] = None) -> str:
    """Return the configured database schema path."""
    return load_config(config_path).schema_path


class MindTaskDB:
    """SQLite-backed task database."""

    def __init__(self, initialize: bool = True, config_path: Optional[str] = None):
        self.config = load_config(config_path)
        self.db_path = self.config.database_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if initialize:
            self.initialize_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _row_dict(self, conn: sqlite3.Connection, table: str, row_id: int) -> Optional[Dict[str, Any]]:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return dict(row) if row else None

    def _task_snapshot(self, conn: sqlite3.Connection, task_id: int) -> Optional[Dict[str, Any]]:
        task = self._row_dict(conn, "tasks", task_id)
        if not task:
            return None
        rows = conn.execute(
            "SELECT tag_id FROM task_tags WHERE task_id = ? ORDER BY tag_id",
            (task_id,),
        ).fetchall()
        return {"task": task, "tag_ids": [row["tag_id"] for row in rows]}

    def _project_snapshot(self, conn: sqlite3.Connection, project_id: int) -> Optional[Dict[str, Any]]:
        project = self._row_dict(conn, "projects", project_id)
        if not project:
            return None
        rows = conn.execute(
            "SELECT id FROM tasks WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        return {"project": project, "task_ids": [row["id"] for row in rows]}

    def _tag_snapshot(self, conn: sqlite3.Connection, tag_id: int) -> Optional[Dict[str, Any]]:
        tag = self._row_dict(conn, "tags", tag_id)
        if not tag:
            return None
        rows = conn.execute(
            "SELECT task_id FROM task_tags WHERE tag_id = ? ORDER BY task_id",
            (tag_id,),
        ).fetchall()
        return {"tag": tag, "task_ids": [row["task_id"] for row in rows]}

    def _record_history(
        self,
        conn: sqlite3.Connection,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]],
    ) -> None:
        conn.execute(
            """
            INSERT INTO operation_history (action, entity_type, entity_id, before_json, after_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_type,
                entity_id,
                json.dumps(before, ensure_ascii=False, sort_keys=True) if before is not None else None,
                json.dumps(after, ensure_ascii=False, sort_keys=True) if after is not None else None,
            ),
        )

    def _insert_row(self, conn: sqlite3.Connection, table: str, data: Dict[str, Any]) -> None:
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [data[column] for column in columns],
        )

    def _restore_task_snapshot(self, conn: sqlite3.Connection, snapshot: Dict[str, Any]) -> None:
        self._insert_row(conn, "tasks", snapshot["task"])
        conn.execute("DELETE FROM task_tags WHERE task_id = ?", (snapshot["task"]["id"],))
        for tag_id in snapshot.get("tag_ids", []):
            conn.execute(
                "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                (snapshot["task"]["id"], tag_id),
            )

    def _restore_project_snapshot(self, conn: sqlite3.Connection, snapshot: Dict[str, Any]) -> None:
        self._insert_row(conn, "projects", snapshot["project"])
        for task_id in snapshot.get("task_ids", []):
            conn.execute("UPDATE tasks SET project_id = ? WHERE id = ?", (snapshot["project"]["id"], task_id))

    def _restore_tag_snapshot(self, conn: sqlite3.Connection, snapshot: Dict[str, Any]) -> None:
        self._insert_row(conn, "tags", snapshot["tag"])
        for task_id in snapshot.get("task_ids", []):
            conn.execute(
                "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                (task_id, snapshot["tag"]["id"]),
            )

    def initialize_database(self) -> None:
        """Create tables and views if they do not exist."""
        schema_path = self.config.schema_path
        if not os.path.exists(schema_path):
            return

        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = fh.read()

        with self._connect() as conn:
            conn.executescript(schema)

    # Project operations
    def create_project(self, name: str, description: str = "", color: str = "#007BFF") -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO projects (name, description, color) VALUES (?, ?, ?)",
                (name, description, color),
            )
            project_id = int(cursor.lastrowid)
            self._record_history(conn, "create", "project", project_id, None, self._project_snapshot(conn, project_id))
            return project_id

    def get_projects(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
            return [dict(row) for row in rows]

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def update_project(self, project_id: int, **kwargs: Any) -> bool:
        allowed = {"name", "description", "color"}
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return False

        values.append(project_id)
        with self._connect() as conn:
            before = self._project_snapshot(conn, project_id)
            cursor = conn.execute(
                f"UPDATE projects SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            changed = cursor.rowcount > 0
            if changed:
                self._record_history(conn, "update", "project", project_id, before, self._project_snapshot(conn, project_id))
            return changed

    def delete_project(self, project_id: int) -> bool:
        with self._connect() as conn:
            before = self._project_snapshot(conn, project_id)
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            changed = cursor.rowcount > 0
            if changed:
                self._record_history(conn, "delete", "project", project_id, before, None)
            return changed

    # Task operations
    def create_task(
        self,
        title: str,
        description: str = "",
        project_id: Optional[int] = None,
        priority: int = 0,
        status: int = 0,
        due_date: Optional[str] = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (title, description, project_id, priority, status, due_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, description, project_id, priority, status, due_date),
            )
            task_id = int(cursor.lastrowid)
            self._record_history(conn, "create", "task", task_id, None, self._task_snapshot(conn, task_id))
            return task_id

    def get_tasks(
        self,
        project_id: Optional[int] = None,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM task_details WHERE 1=1"
        params: List[Any] = []

        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if priority is not None:
            query += " AND priority = ?"
            params.append(priority)

        query += " ORDER BY priority DESC, due_date IS NULL, due_date ASC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM task_details WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def get_tasks_with_tags(self, task_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM tasks_with_tags"
        params: List[Any] = []

        if task_id is not None:
            query += " WHERE id = ?"
            params.append(task_id)

        query += " ORDER BY priority DESC, due_date IS NULL, due_date ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_task(self, task_id: int, **kwargs: Any) -> bool:
        allowed = {"title", "description", "project_id", "priority", "status", "due_date"}
        fields = []
        values = []

        for key, value in kwargs.items():
            if key in allowed:
                fields.append(f"{key} = ?")
                values.append(value)
            elif key == "completed":
                fields.append("status = ?")
                fields.append("completed_at = ?")
                values.append(2 if value else 0)
                values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S") if value else None)

        if not fields:
            return False

        values.append(task_id)
        with self._connect() as conn:
            before = self._task_snapshot(conn, task_id)
            cursor = conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            changed = cursor.rowcount > 0
            if changed:
                self._record_history(conn, "update", "task", task_id, before, self._task_snapshot(conn, task_id))
            return changed

    def complete_task(self, task_id: int) -> bool:
        return self.update_task(
            task_id,
            completed=True,
        )

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            before = self._task_snapshot(conn, task_id)
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            changed = cursor.rowcount > 0
            if changed:
                self._record_history(conn, "delete", "task", task_id, before, None)
            return changed

    # Tag operations
    def create_tag(self, name: str, color: str = "#6C757D") -> int:
        with self._connect() as conn:
            existed = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            conn.execute(
                "INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
                (name, color),
            )
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            tag_id = int(row["id"])
            if existed is None:
                self._record_history(conn, "create", "tag", tag_id, None, self._tag_snapshot(conn, tag_id))
            return tag_id

    def get_tags(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
            return [dict(row) for row in rows]

    def add_tag_to_task(self, task_id: int, tag_id: int) -> bool:
        with self._connect() as conn:
            try:
                before = {"task_id": task_id, "tag_id": tag_id, "exists": False}
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                    (task_id, tag_id),
                )
                changed = cursor.rowcount > 0
                if changed:
                    after = {"task_id": task_id, "tag_id": tag_id, "exists": True}
                    self._record_history(conn, "create", "task_tag", None, before, after)
                return changed
            except sqlite3.IntegrityError:
                return False

    def remove_tag_from_task(self, task_id: int, tag_id: int) -> bool:
        with self._connect() as conn:
            before = {"task_id": task_id, "tag_id": tag_id, "exists": True}
            cursor = conn.execute(
                "DELETE FROM task_tags WHERE task_id = ? AND tag_id = ?",
                (task_id, tag_id),
            )
            changed = cursor.rowcount > 0
            if changed:
                self._record_history(conn, "delete", "task_tag", None, before, {"task_id": task_id, "tag_id": tag_id, "exists": False})
            return changed

    def get_task_tags(self, task_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.* FROM tags t
                JOIN task_tags tt ON t.id = tt.tag_id
                WHERE tt.task_id = ?
                ORDER BY t.name
                """,
                (task_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    # Reports
    def get_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            stats: Dict[str, Any] = {}

            stats["total_tasks"] = conn.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]

            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END), 0) AS completed,
                    COALESCE(SUM(CASE WHEN status < 2 THEN 1 ELSE 0 END), 0) AS pending
                FROM tasks
                """
            ).fetchone()
            stats["completed_tasks"] = row["completed"]
            stats["pending_tasks"] = row["pending"]

            rows = conn.execute(
                """
                SELECT priority, COUNT(*) AS count
                FROM tasks
                GROUP BY priority
                ORDER BY priority DESC
                """
            ).fetchall()
            stats["priority_stats"] = [dict(row) for row in rows]

            rows = conn.execute(
                """
                SELECT
                    p.name AS project_name,
                    COUNT(t.id) AS total,
                    COALESCE(SUM(CASE WHEN t.status = 2 THEN 1 ELSE 0 END), 0) AS completed
                FROM projects p
                LEFT JOIN tasks t ON p.id = t.project_id
                GROUP BY p.id, p.name
                ORDER BY p.name
                """
            ).fetchall()
            stats["project_stats"] = [dict(row) for row in rows]

            stats["upcoming_tasks"] = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM tasks
                WHERE due_date <= datetime('now', '+3 days')
                  AND status < 2
                """
            ).fetchone()["count"]

            return stats

    def search_tasks(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        pattern = f"%{keyword}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_details
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY priority DESC, due_date IS NULL, due_date ASC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_history(self, limit: int = 50, include_undone: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM operation_history"
        params: List[Any] = []
        if not include_undone:
            query += " WHERE undone_at IS NULL"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def undo_last_operation(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM operation_history
                WHERE undone_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None

            history = dict(row)
            before = json.loads(history["before_json"]) if history.get("before_json") else None
            after = json.loads(history["after_json"]) if history.get("after_json") else None
            action = history["action"]
            entity_type = history["entity_type"]
            entity_id = history["entity_id"]

            if entity_type == "task":
                if action == "create":
                    conn.execute("DELETE FROM tasks WHERE id = ?", (entity_id,))
                elif action == "delete":
                    self._restore_task_snapshot(conn, before)
                elif action == "update":
                    self._restore_task_snapshot(conn, before)
            elif entity_type == "project":
                if action == "create":
                    conn.execute("DELETE FROM projects WHERE id = ?", (entity_id,))
                elif action == "delete":
                    self._restore_project_snapshot(conn, before)
                elif action == "update":
                    self._restore_project_snapshot(conn, before)
            elif entity_type == "tag":
                if action == "create":
                    conn.execute("DELETE FROM tags WHERE id = ?", (entity_id,))
                elif action == "delete":
                    self._restore_tag_snapshot(conn, before)
                elif action == "update":
                    self._restore_tag_snapshot(conn, before)
            elif entity_type == "task_tag":
                snapshot = before if action == "delete" else after
                if action == "create":
                    conn.execute(
                        "DELETE FROM task_tags WHERE task_id = ? AND tag_id = ?",
                        (snapshot["task_id"], snapshot["tag_id"]),
                    )
                elif action == "delete":
                    conn.execute(
                        "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                        (snapshot["task_id"], snapshot["tag_id"]),
                    )
            else:
                raise ValueError(f"Unsupported history entity type: {entity_type}")

            conn.execute(
                "UPDATE operation_history SET undone_at = CURRENT_TIMESTAMP WHERE id = ?",
                (history["id"],),
            )
            return history

def example_usage() -> None:
    db = MindTaskDB()
    stats = db.get_stats()
    print("MindTask database is ready.")
    print(f"Total tasks: {stats['total_tasks']}")
    print(f"Completed tasks: {stats['completed_tasks']}")
    print(f"Pending tasks: {stats['pending_tasks']}")

    due_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    task_id = db.create_task("Example task", description="Created by example_usage", due_date=due_date)
    print(f"Created task #{task_id}")


if __name__ == "__main__":
    example_usage()
