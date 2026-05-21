"""Database file operations for the desktop UI."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ...core import MindTaskDB
from ...core.config import load_config


SQLITE_HEADER = b"SQLite format 3\x00"
SQLITE_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
REQUIRED_TABLE_COLUMNS = {
    "projects": {"id", "name", "description", "color", "created_at", "updated_at"},
    "tasks": {
        "id",
        "title",
        "description",
        "project_id",
        "priority",
        "status",
        "due_date",
        "completed_at",
        "created_at",
        "updated_at",
    },
    "operation_history": {"id", "action", "entity_type", "entity_id", "before_json", "after_json", "created_at"},
}


class DatabasePathError(ValueError):
    """Validation error carrying an i18n key and optional format values."""

    def __init__(self, key: str, **kwargs: Any) -> None:
        super().__init__(key)
        self.key = key
        self.kwargs = kwargs


@dataclass(frozen=True)
class NewDatabaseTarget:
    path: Path
    exists: bool


class DatabaseFileService:
    """High-level database file workflow used by settings and setup UI."""

    def __init__(self, config_path: str, language: Optional[str] = None) -> None:
        self.config_path = config_path
        self.language = language

    def open_existing_database(self, path_text: str) -> MindTaskDB:
        path = self._validate_existing_database_path(path_text)
        db = self._open_database_from_path(path)
        db.get_tasks(limit=1)
        return db

    def inspect_new_database_target(self, path_text: str) -> NewDatabaseTarget:
        path = self._validate_database_output_path(path_text, allow_existing_file=True)
        return NewDatabaseTarget(path=path, exists=path.exists())

    def create_database(self, path_text: str, overwrite: bool = False, with_sample_data: bool = True) -> MindTaskDB:
        path = self._validate_database_output_path(path_text, allow_existing_file=overwrite)
        if path.exists() and not overwrite:
            raise DatabasePathError("database_file_exists")
        try:
            if path.exists():
                path.unlink()
            db = self._open_database_from_path(path)
            if with_sample_data:
                db.create_sample_data()
            db.get_tasks(limit=1)
            return db
        except DatabasePathError:
            raise
        except Exception as exc:
            raise DatabasePathError("could_not_create_database", error=exc) from exc

    def default_backup_path(self, source_path_text: str) -> Path:
        source = self._validate_existing_database_path(source_path_text)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return source.with_name(f"{source.stem}-backup-{timestamp}{source.suffix or '.db'}")

    def backup_database(self, source_path_text: str, target_path_text: str) -> Path:
        source = self._validate_existing_database_path(source_path_text)
        target = self._validate_database_output_path(target_path_text, allow_existing_file=True)
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            raise DatabasePathError("could_not_backup_database", error=exc) from exc
        return target

    def _open_database_from_path(self, database_path: Path) -> MindTaskDB:
        config = load_config(self.config_path)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".ini", delete=False) as fh:
            temp_config_path = fh.name
            fh.write("[database]\n")
            fh.write(f"path = {database_path}\n\n")
            fh.write("[ui]\n")
            fh.write(f"theme = {config.ui_theme}\n")
            fh.write(f"language = {self.language or config.ui_language}\n")
            fh.write(f"smart_task_sorting = {'true' if config.smart_task_sorting else 'false'}\n")
            fh.write(f"hide_completed_tasks = {'true' if config.hide_completed_tasks else 'false'}\n")
        try:
            return MindTaskDB(config_path=temp_config_path)
        finally:
            Path(temp_config_path).unlink(missing_ok=True)

    def _validate_existing_database_path(self, path_text: str) -> Path:
        path = self._normalize_database_path(path_text)
        try:
            self._require_sqlite_suffix(path)
            if not path.exists():
                raise DatabasePathError("database_file_not_found")
            if not path.is_file():
                raise DatabasePathError("database_path_must_be_file")
            if path.stat().st_size == 0:
                raise DatabasePathError("database_file_empty")
            with path.open("rb") as fh:
                if fh.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                    raise DatabasePathError("invalid_sqlite_database")
        except OSError as exc:
            raise DatabasePathError("could_not_open_database", error=exc) from exc

        try:
            with closing(sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True)) as conn:
                quick_check = conn.execute("PRAGMA quick_check").fetchone()
                if not quick_check or quick_check[0] != "ok":
                    raise DatabasePathError("database_integrity_check_failed")
                self._validate_mindtask_schema(conn)
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("ROLLBACK")
        except DatabasePathError:
            raise
        except sqlite3.DatabaseError as exc:
            raise DatabasePathError("database_not_writable_or_locked", error=exc) from exc
        except OSError as exc:
            raise DatabasePathError("could_not_open_database", error=exc) from exc
        return path

    def _validate_database_output_path(self, path_text: str, allow_existing_file: bool = False) -> Path:
        path = self._normalize_database_path(path_text)
        self._require_sqlite_suffix(path)
        if path.exists():
            if not path.is_file():
                raise DatabasePathError("database_path_must_be_file")
            if not allow_existing_file:
                raise DatabasePathError("database_file_exists")

        parent = path.parent
        try:
            if not parent.exists():
                raise DatabasePathError("database_parent_not_found")
            if not parent.is_dir():
                raise DatabasePathError("database_parent_not_directory")
            with tempfile.NamedTemporaryFile(prefix=".mindtask-write-test-", dir=str(parent), delete=True):
                pass
        except DatabasePathError:
            raise
        except OSError as exc:
            raise DatabasePathError("database_parent_not_writable", error=exc) from exc
        return path

    def _normalize_database_path(self, path_text: str) -> Path:
        path = Path(os.path.expandvars(os.path.expanduser(path_text)))
        if not path.is_absolute():
            raise DatabasePathError("database_path_must_be_absolute")
        return path.resolve(strict=False)

    def _require_sqlite_suffix(self, path: Path) -> None:
        if path.suffix.casefold() not in SQLITE_DATABASE_SUFFIXES:
            raise DatabasePathError("database_extension_required")

    def _validate_mindtask_schema(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        table_names = {row[0] for row in rows}
        if not set(REQUIRED_TABLE_COLUMNS).issubset(table_names):
            raise DatabasePathError("not_mindtask_database")

        for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if not required_columns.issubset(columns):
                raise DatabasePathError("not_mindtask_database")
