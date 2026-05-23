#!/usr/bin/env python3
"""Core database access for MindTask."""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import load_config


STATUS_NOT_STARTED = 0
STATUS_IN_PROGRESS = 1
STATUS_SUSPENDED = 2
STATUS_COMPLETED = 3
DUE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DUE_MODE_NONE = "none"
DUE_MODE_ALL_DAY = "all_day"
DUE_MODE_EXACT_TIME = "exact_time"
DUE_MODES = {DUE_MODE_NONE, DUE_MODE_ALL_DAY, DUE_MODE_EXACT_TIME}


def current_timestamp() -> str:
    """Return MindTask's local timestamp storage format."""
    return datetime.now().strftime(DUE_DATE_FORMAT)


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that closes when leaving a with block."""

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        self.close()


class DatabaseMissingError(FileNotFoundError):
    """Raised when configured database is missing outside an explicit create flow."""


class DatabaseInvalidError(RuntimeError):
    """Raised when configured database exists but is not a usable MindTask database."""


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


def normalize_task_due(due_date: Optional[str], due_mode: Optional[str] = None) -> tuple[Optional[str], str]:
    """Validate and normalize task due fields for storage."""
    if due_mode is None:
        due_mode = DUE_MODE_EXACT_TIME if due_date else DUE_MODE_NONE
    if due_mode not in DUE_MODES:
        raise ValueError("due_mode must be one of none, all_day, exact_time")
    if due_mode == DUE_MODE_NONE:
        return None, DUE_MODE_NONE

    due_date = normalize_due_date(due_date)
    if due_date is None:
        raise ValueError("due_date is required when due_mode is all_day or exact_time")
    if due_mode == DUE_MODE_ALL_DAY:
        due = datetime.strptime(due_date, DUE_DATE_FORMAT)
        return due.replace(hour=0, minute=0, second=0).strftime(DUE_DATE_FORMAT), DUE_MODE_ALL_DAY
    return due_date, DUE_MODE_EXACT_TIME


class MindTaskDB:
    """SQLite-backed task database."""

    def __init__(self, initialize: bool = True, config_path: Optional[str] = None, create_if_missing: bool = False):
        self.config = load_config(config_path)
        self.db_path = self.config.database_path
        self.create_if_missing = create_if_missing
        if create_if_missing:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        elif not os.path.exists(self.db_path):
            raise DatabaseMissingError(self.db_path)
        else:
            self._validate_database_available()
        if initialize:
            self.initialize_database()

    def _connect(self) -> sqlite3.Connection:
        if not self.create_if_missing:
            self._validate_database_available()
            connect_target = f"{Path(self.db_path).resolve(strict=False).as_uri()}?mode=rw"
            conn = sqlite3.connect(connect_target, uri=True, factory=ClosingConnection)
        else:
            conn = sqlite3.connect(self.db_path, factory=ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _validate_database_available(self) -> None:
        path = Path(self.db_path)
        if not path.exists():
            raise DatabaseMissingError(self.db_path)
        if not path.is_file():
            raise DatabaseInvalidError(self.db_path)
        try:
            if path.stat().st_size == 0:
                raise DatabaseInvalidError(self.db_path)
            with path.open("rb") as fh:
                if fh.read(16) != b"SQLite format 3\x00":
                    raise DatabaseInvalidError(self.db_path)
            with sqlite3.connect(f"{path.resolve(strict=False).as_uri()}?mode=rw", uri=True) as conn:
                quick_check = conn.execute("PRAGMA quick_check").fetchone()
                if not quick_check or quick_check[0] != "ok":
                    raise DatabaseInvalidError(self.db_path)
                self._validate_mindtask_schema(conn)
        except (DatabaseMissingError, DatabaseInvalidError):
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            raise DatabaseInvalidError(self.db_path) from exc

    def _validate_mindtask_schema(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        table_names = {row[0] for row in rows}
        if not {"projects", "tasks", "operation_history"}.issubset(table_names):
            raise DatabaseInvalidError(self.db_path)

    def _row_dict(self, conn: sqlite3.Connection, table: str, row_id: int) -> Optional[Dict[str, Any]]:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return dict(row) if row else None

    def _task_snapshot(self, conn: sqlite3.Connection, task_id: int) -> Optional[Dict[str, Any]]:
        task = self._row_dict(conn, "tasks", task_id)
        if not task:
            return None
        return {"task": task}

    def _project_snapshot(self, conn: sqlite3.Connection, project_id: int) -> Optional[Dict[str, Any]]:
        project = self._row_dict(conn, "projects", project_id)
        if not project:
            return None
        rows = conn.execute(
            "SELECT id FROM tasks WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        return {"project": project, "task_ids": [row["id"] for row in rows]}

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
            INSERT INTO operation_history (action, entity_type, entity_id, before_json, after_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_type,
                entity_id,
                json.dumps(before, ensure_ascii=False, sort_keys=True) if before is not None else None,
                json.dumps(after, ensure_ascii=False, sort_keys=True) if after is not None else None,
                current_timestamp(),
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

    def _restore_project_snapshot(self, conn: sqlite3.Connection, snapshot: Dict[str, Any]) -> None:
        self._insert_row(conn, "projects", snapshot["project"])
        for task_id in snapshot.get("task_ids", []):
            conn.execute("UPDATE tasks SET project_id = ? WHERE id = ?", (snapshot["project"]["id"], task_id))

    def initialize_database(self) -> None:
        """Create tables and views if they do not exist."""
        schema_path = self.config.schema_path
        if not os.path.exists(schema_path):
            return

        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = fh.read()

        with self._connect() as conn:
            conn.executescript(schema)
            self._ensure_task_due_mode_column(conn)
            self._drop_obsolete_tag_schema(conn)
            if self._migrate_task_status_constraint(conn):
                conn.executescript(schema)
                self._ensure_task_due_mode_column(conn)
                self._drop_obsolete_tag_schema(conn)

    def _drop_obsolete_tag_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP VIEW IF EXISTS tasks_with_tags;
            DROP TABLE IF EXISTS task_tags;
            DROP TABLE IF EXISTS tags;
            """
        )

    def _ensure_task_due_mode_column(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "due_mode" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN due_mode TEXT DEFAULT 'none'")
            conn.execute(
                """
                UPDATE tasks
                SET due_mode = CASE WHEN due_date IS NULL THEN 'none' ELSE 'exact_time' END
                WHERE due_mode IS NULL OR due_mode = 'none'
                """
            )

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
                due_mode TEXT DEFAULT 'none' CHECK (due_mode IN ('none', 'all_day', 'exact_time')),
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
            );

            INSERT INTO tasks_new (
                id, title, description, project_id, priority, status,
                due_date, due_mode, completed_at, created_at, updated_at
            )
            SELECT
                id, title, description, project_id, priority,
                CASE WHEN status = 2 THEN 3 ELSE status END,
                due_date,
                CASE WHEN due_date IS NULL THEN 'none' ELSE 'exact_time' END,
                completed_at, created_at, updated_at
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
            now = current_timestamp()
            cursor = conn.execute(
                """
                INSERT INTO projects (name, description, color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, description, color, now, now),
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

        with self._connect() as conn:
            before = self._project_snapshot(conn, project_id)
            if not before:
                return False
            project_before = before["project"]
            filtered_fields = []
            filtered_values = []
            for field, value in zip(fields, values):
                key = field.split(" = ", 1)[0]
                if project_before.get(key) != value:
                    filtered_fields.append(field)
                    filtered_values.append(value)
            if not filtered_fields:
                return True
            filtered_fields.append("updated_at = ?")
            filtered_values.append(current_timestamp())
            filtered_values.append(project_id)
            cursor = conn.execute(
                f"UPDATE projects SET {', '.join(filtered_fields)} WHERE id = ?",
                filtered_values,
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
        due_mode: Optional[str] = None,
    ) -> int:
        due_date, due_mode = normalize_task_due(due_date, due_mode)
        with self._connect() as conn:
            now = current_timestamp()
            completed_at = now if int(status) == STATUS_COMPLETED else None
            cursor = conn.execute(
                """
                INSERT INTO tasks (
                    title, description, project_id, priority, status,
                    due_date, due_mode, completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, description, project_id, priority, status, due_date, due_mode, completed_at, now, now),
            )
            task_id = int(cursor.lastrowid)
            self._record_history(conn, "create", "task", task_id, None, self._task_snapshot(conn, task_id))
            return task_id

    def get_tasks(
        self,
        project_id: Optional[int] = None,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        limit: Optional[int] = None,
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

        query += " ORDER BY id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM task_details WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def update_task(self, task_id: int, **kwargs: Any) -> bool:
        allowed = {"title", "description", "project_id", "priority", "status"}
        updates: Dict[str, Any] = {}

        if "due_date" in kwargs or "due_mode" in kwargs:
            due_date, due_mode = normalize_task_due(kwargs.get("due_date"), kwargs.get("due_mode"))
            updates["due_date"] = due_date
            updates["due_mode"] = due_mode

        for key, value in kwargs.items():
            if key == "status":
                status = int(value)
                updates["status"] = status
            elif key in allowed:
                updates[key] = value
            elif key == "completed":
                updates["status"] = STATUS_COMPLETED if value else STATUS_NOT_STARTED

        if not updates:
            return False

        with self._connect() as conn:
            before = self._task_snapshot(conn, task_id)
            if not before:
                return False
            task_before = before["task"]
            if "status" in updates:
                previous_status = int(task_before.get("status") or STATUS_NOT_STARTED)
                next_status = int(updates["status"])
                if next_status == STATUS_COMPLETED and previous_status != STATUS_COMPLETED:
                    updates["completed_at"] = current_timestamp()
                elif next_status != STATUS_COMPLETED:
                    updates["completed_at"] = None

            changed_updates = {
                key: value
                for key, value in updates.items()
                if task_before.get(key) != value
            }
            if not changed_updates:
                return True
            changed_updates["updated_at"] = current_timestamp()
            fields = [f"{key} = ?" for key in changed_updates]
            values = list(changed_updates.values())
            values.append(task_id)
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

    def search_tasks(self, keyword: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        pattern = f"%{keyword}%"
        query = """
            SELECT * FROM task_details
            WHERE title LIKE ? OR description LIKE ?
            ORDER BY id ASC
        """
        params: List[Any] = [pattern, pattern]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_history(self, limit: Optional[int] = None, include_undone: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM operation_history"
        params: List[Any] = []
        if not include_undone:
            query += " WHERE undone_at IS NULL"
        query += " ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_task_history(self, task_id: int, limit: int = 10, include_undone: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM operation_history WHERE entity_type = 'task' AND entity_id = ?"
        params: List[Any] = [task_id]
        if not include_undone:
            query += " AND undone_at IS NULL"
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
        elif entity_type in {"tag", "task_tag"}:
            pass
        else:
            raise ValueError(f"Unsupported history entity type: {entity_type}")

        conn.execute(
            "UPDATE operation_history SET undone_at = ? WHERE id = ?",
            (current_timestamp(), history["id"]),
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
