"""Database schema versioning and migrations for MindTask."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..version import __version__ as APP_VERSION


MigrationStep = Callable[[sqlite3.Connection], None]
_UNSET = object()


def unspecified_migration_start_version() -> object:
    return _UNSET


@dataclass(frozen=True)
class Migration:
    from_version: Optional[str]
    apply: MigrationStep


class DatabaseMigrationRequiredError(RuntimeError):
    """Raised when a usable MindTask database needs an explicit schema migration."""

    def __init__(self, database_path: str, current_version: Optional[str], target_version: str = APP_VERSION):
        super().__init__(database_path)
        self.database_path = database_path
        self.current_version = current_version
        self.target_version = target_version


def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def database_schema_version(conn: sqlite3.Connection) -> Optional[str]:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'database_metadata'"
    ).fetchone()
    if not table:
        return None
    row = conn.execute("SELECT value FROM database_metadata WHERE key = 'schema_version'").fetchone()
    if not row:
        return None
    try:
        return str(row["value"])
    except (IndexError, TypeError):
        return str(row[0])


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
        "due_mode",
        "completed_at",
        "created_at",
        "updated_at",
    },
    "operation_history": {
        "id",
        "action",
        "entity_type",
        "entity_id",
        "before_json",
        "after_json",
        "source",
        "ai_batch_id",
        "undone_at",
        "created_at",
    },
    "ai_chat_sessions": {"id", "title", "created_at", "updated_at"},
    "ai_chat_messages": {"id", "session_id", "role", "content", "metadata_json", "created_at"},
    "ai_operation_batches": {
        "id",
        "session_id",
        "user_message_id",
        "model",
        "before_history_id",
        "after_history_id",
        "operation_summary_json",
        "status",
        "error",
        "created_at",
        "completed_at",
        "undone_at",
    },
}
REQUIRED_VIEWS = {"task_details"}


def has_required_schema_elements(conn: sqlite3.Connection) -> bool:
    """Return whether the database already has the elements this app needs."""
    tables = {
        row["name"] if isinstance(row, sqlite3.Row) else row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    if not set(REQUIRED_TABLE_COLUMNS).issubset(tables):
        return False
    for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
        columns = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if not required_columns.issubset(columns):
            return False
    views = {
        row["name"] if isinstance(row, sqlite3.Row) else row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall()
    }
    return REQUIRED_VIEWS.issubset(views)


def migration_start_version(version: Optional[str]) -> Optional[str]:
    """Return the migration start key for a stored schema version."""
    if version is None:
        return None
    parts = str(version).strip().split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        return version
    if (major, minor) <= (1, 2):
        return None
    return version


def assert_current_schema_version(conn: sqlite3.Connection, database_path: str, allow_migration: bool = False) -> None:
    if has_required_schema_elements(conn):
        return
    version = database_schema_version(conn)
    if version == APP_VERSION:
        return
    start_version = migration_start_version(version)
    if allow_migration:
        _ensure_migration_path(start_version, database_path)
        return
    raise DatabaseMigrationRequiredError(database_path, version, APP_VERSION)


def _ensure_migration_path(version: Optional[str], database_path: str) -> None:
    if version == APP_VERSION:
        return
    if version not in MIGRATION_START_INDEX:
        raise DatabaseMigrationRequiredError(database_path, version, APP_VERSION)


def prepare_existing_schema_for_migrations(conn: sqlite3.Connection) -> None:
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    if "operation_history" in tables:
        ensure_operation_history_ai_columns(conn)


def ensure_operation_history_ai_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(operation_history)").fetchall()}
    if "source" not in columns:
        conn.execute("ALTER TABLE operation_history ADD COLUMN source TEXT DEFAULT 'user'")
    if "ai_batch_id" not in columns:
        conn.execute("ALTER TABLE operation_history ADD COLUMN ai_batch_id INTEGER")


def ensure_ai_metadata_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
            content TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ai_operation_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            user_message_id INTEGER,
            model TEXT DEFAULT '',
            before_history_id INTEGER,
            after_history_id INTEGER,
            operation_summary_json TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'running',
            error TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            completed_at TIMESTAMP,
            undone_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES ai_chat_sessions (id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_operation_history_ai_batch_id ON operation_history(ai_batch_id);
        CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session_id ON ai_chat_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_ai_operation_batches_session_id ON ai_operation_batches(session_id);
        """
    )


def set_database_schema_version(conn: sqlite3.Connection, version: str = APP_VERSION) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS database_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO database_metadata (key, value, updated_at)
        VALUES ('schema_version', ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (version, current_timestamp()),
    )


def migrate_from_legacy(conn: sqlite3.Connection) -> None:
    prepare_existing_schema_for_migrations(conn)
    ensure_operation_history_ai_columns(conn)
    ensure_ai_metadata_schema(conn)


MIGRATIONS: list[Migration] = [
    Migration(None, migrate_from_legacy),
]
MIGRATION_START_INDEX: dict[Optional[str], int] = {
    migration.from_version: index
    for index, migration in enumerate(MIGRATIONS)
}


def available_migration_start_versions() -> list[Optional[str]]:
    return list(MIGRATION_START_INDEX)


def migrate_to_current(
    conn: sqlite3.Connection,
    database_path: str = "<database>",
    *,
    assumed_start_version: Any = _UNSET,
) -> None:
    if has_required_schema_elements(conn):
        return
    version = database_schema_version(conn)
    if version == APP_VERSION:
        return
    start_version = (
        migration_start_version(assumed_start_version)
        if assumed_start_version is not _UNSET
        else migration_start_version(version)
    )
    if start_version not in MIGRATION_START_INDEX:
        raise DatabaseMigrationRequiredError(database_path, version, APP_VERSION)

    start_index = MIGRATION_START_INDEX[start_version]
    if MIGRATIONS[start_index].from_version != start_version:
        raise DatabaseMigrationRequiredError(database_path, version, APP_VERSION)
    for migration in MIGRATIONS[start_index:]:
        migration.apply(conn)

    set_database_schema_version(conn, APP_VERSION)
