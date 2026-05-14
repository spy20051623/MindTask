"""Configuration loading for MindTask."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "mindtask.ini"


@dataclass(frozen=True)
class MindTaskConfig:
    database_path: str
    schema_path: str
    default_task_limit: int = 100
    default_search_limit: int = 20


def resolve_project_path(value: str) -> str:
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def load_config(config_path: Optional[str] = None) -> MindTaskConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    parser = configparser.ConfigParser()

    if path.exists():
        parser.read(path, encoding="utf-8-sig")

    database_path = parser.get("database", "path", fallback="data/mindtask.db")
    schema_path = parser.get("database", "schema", fallback="sql/mindtask_db_schema.sql")
    default_task_limit = parser.getint("app", "default_task_limit", fallback=100)
    default_search_limit = parser.getint("app", "default_search_limit", fallback=20)

    return MindTaskConfig(
        database_path=resolve_project_path(database_path),
        schema_path=resolve_project_path(schema_path),
        default_task_limit=default_task_limit,
        default_search_limit=default_search_limit,
    )
