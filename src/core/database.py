#!/usr/bin/env python3
"""Core database access for MindTask."""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import load_config


STATUS_NOT_STARTED = 0
STATUS_IN_PROGRESS = 1
STATUS_SUSPENDED = 2
STATUS_COMPLETED = 3
DUE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that closes when leaving a with block."""

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        self.close()


def get_database_path(config_path: Optional[str] = None) -> str:
    """Return the configured SQLite database path."""
    return load_config(config_path).database_path


def get_schema_path(config_path: Optional[str] = None) -> str:
    """Return the configured database schema path."""
    return load_config(config_path).schema_path


def normalize_due_date(value: Optional[str]) -> Optional[str]:
    """Validate and return a due date in MindTask's storage format."""
    if value is None:
        return None
    try:
        datetime.strptime(value, DUE_DATE_FORMAT)
    except ValueError as exc:
        raise ValueError("due_date must use format YYYY-MM-DD HH:MM:SS") from exc
    return value


class MindTaskDB:
    """SQLite-backed task database."""

    def __init__(self, initialize: bool = True, config_path: Optional[str] = None):
        self.config = load_config(config_path)
        self.db_path = self.config.database_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if initialize:
            self.initialize_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, factory=ClosingConnection)
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
            if self._migrate_task_status_constraint(conn):
                conn.executescript(schema)

    def _migrate_task_status_constraint(self, conn: sqlite3.Connection) -> bool:
        table_sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
        if not table_sql_row:
            return False

        table_sql = table_sql_row["sql"] or ""
        if "status BETWEEN 0 AND 2" not in table_sql:
            return False

        conn.executescript(
            """
            PRAGMA foreign_keys = OFF;

            DROP VIEW IF EXISTS task_details;
            DROP VIEW IF EXISTS tasks_with_tags;

            CREATE TABLE tasks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                project_id INTEGER,
                priority INTEGER DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
                status INTEGER DEFAULT 0 CHECK (status BETWEEN 0 AND 3),
                due_date TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
            );

            INSERT INTO tasks_new (
                id, title, description, project_id, priority, status,
                due_date, completed_at, created_at, updated_at
            )
            SELECT
                id, title, description, project_id, priority,
                CASE WHEN status = 2 THEN 3 ELSE status END,
                due_date, completed_at, created_at, updated_at
            FROM tasks;

            DROP TABLE tasks;
            ALTER TABLE tasks_new RENAME TO tasks;

            PRAGMA foreign_keys = ON;
            """
        )
        return True

    # Project operations
    def create_project(self, name: str, description: str = "", color: str = "#007BFF") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Project name is required.")
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
            rows = conn.execute("SELECT * FROM projects ORDER BY id ASC").fetchall()
            return [dict(row) for row in rows]

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def get_project_summaries(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.description,
                    p.color,
                    p.created_at,
                    p.updated_at,
                    COUNT(t.id) AS task_count,
                    COALESCE(SUM(CASE WHEN t.status < 3 THEN 1 ELSE 0 END), 0) AS active_task_count,
                    COALESCE(SUM(CASE WHEN t.status = 3 THEN 1 ELSE 0 END), 0) AS completed_task_count
                FROM projects p
                LEFT JOIN tasks t ON p.id = t.project_id
                GROUP BY p.id, p.name, p.description, p.color, p.created_at, p.updated_at
                ORDER BY p.id ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def update_project(self, project_id: int, **kwargs: Any) -> bool:
        allowed = {"name", "description", "color"}
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                if key == "name":
                    value = str(value).strip()
                    if not value:
                        raise ValueError("Project name is required.")
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
            if before and before.get("task_ids"):
                raise ValueError("Project still contains tasks and cannot be deleted.")
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            changed = cursor.rowcount > 0
            if changed:
                self._record_history(conn, "delete", "project", project_id, before, None)
            return changed

    def create_sample_data(self) -> Dict[str, List[int]]:
        """Create starter projects and tasks for a new database."""
        work_id = self.create_project("Work", description="Example work project", color="#2563EB")
        personal_id = self.create_project("Personal", description="Example personal project", color="#16A34A")
        task_ids = [
            self.create_task(
                "Review MindTask",
                description="Explore the task list, detail panel, and project page.",
                project_id=work_id,
                priority=2,
                status=1,
            ),
            self.create_task(
                "Plan next tasks",
                description="Create your own project and add a real task.",
                project_id=work_id,
                priority=1,
                status=0,
            ),
            self.create_task(
                "Try history undo",
                description="Edit a sample task, open History, and undo the change.",
                project_id=personal_id,
                priority=0,
                status=0,
            ),
        ]
        return {"project_ids": [work_id, personal_id], "task_ids": task_ids}

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
        due_date = normalize_due_date(due_date)
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

        query += " ORDER BY id ASC LIMIT ?"
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

        query += " ORDER BY id ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_task(self, task_id: int, **kwargs: Any) -> bool:
        allowed = {"title", "description", "project_id", "priority", "status", "due_date"}
        fields = []
        values = []

        for key, value in kwargs.items():
            if key == "status":
                status = int(value)
                fields.append("status = ?")
                fields.append("completed_at = ?")
                values.append(status)
                values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == STATUS_COMPLETED else None)
            elif key in allowed:
                fields.append(f"{key} = ?")
                values.append(normalize_due_date(value) if key == "due_date" else value)
            elif key == "completed":
                fields.append("status = ?")
                fields.append("completed_at = ?")
                values.append(STATUS_COMPLETED if value else STATUS_NOT_STARTED)
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
                    COALESCE(SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END), 0) AS not_started,
                    COALESCE(SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END), 0) AS in_progress,
                    COALESCE(SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END), 0) AS suspended,
                    COALESCE(SUM(CASE WHEN status = 3 THEN 1 ELSE 0 END), 0) AS completed,
                    COALESCE(SUM(CASE WHEN status < 3 THEN 1 ELSE 0 END), 0) AS pending
                FROM tasks
                """
            ).fetchone()
            stats["not_started_tasks"] = row["not_started"]
            stats["in_progress_tasks"] = row["in_progress"]
            stats["suspended_tasks"] = row["suspended"]
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
                    COALESCE(SUM(CASE WHEN t.status = 3 THEN 1 ELSE 0 END), 0) AS completed
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
                  AND status < 3
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
                ORDER BY id ASC
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
            history = self._next_undoable_history(conn)
            if not history:
                return None
            self._undo_history_item(conn, history)
            return history

    def undo_operations_until(self, history_id: int) -> List[Dict[str, Any]]:
        """Undo operations from newest down to and including history_id."""
        undone: List[Dict[str, Any]] = []
        with self._connect() as conn:
            target = conn.execute(
                "SELECT * FROM operation_history WHERE id = ? AND undone_at IS NULL",
                (history_id,),
            ).fetchone()
            if not target:
                return undone

            while True:
                history = self._next_undoable_history(conn)
                if not history:
                    break
                undone.append(history)
                self._undo_history_item(conn, history)
                if history["id"] == history_id:
                    break
        return undone

    def _next_undoable_history(self, conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            """
            SELECT * FROM operation_history
            WHERE undone_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None

    def _undo_history_item(self, conn: sqlite3.Connection, history: Dict[str, Any]) -> None:
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

def example_usage() -> None:
    db = MindTaskDB()
    stats = db.get_stats()
    print("MindTask database is ready.")
    print(f"Total tasks: {stats['total_tasks']}")
    print(f"Not started: {stats['not_started_tasks']}")
    print(f"In progress: {stats['in_progress_tasks']}")
    print(f"Suspended: {stats['suspended_tasks']}")
    print(f"Completed: {stats['completed_tasks']}")

    task_id = db.create_task("Example task", description="Created by example_usage", due_date="2099-01-01 00:00:00")
    print(f"Created task #{task_id}")


if __name__ == "__main__":
    example_usage()
