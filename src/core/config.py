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
    ui_theme: str = "system"


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
    ui_theme = parser.get("ui", "theme", fallback="system")
    if ui_theme not in {"system", "light", "dark"}:
        ui_theme = "system"

    return MindTaskConfig(
        database_path=resolve_project_path(database_path),
        schema_path=resolve_project_path(schema_path),
        default_task_limit=default_task_limit,
        default_search_limit=default_search_limit,
        ui_theme=ui_theme,
    )


def get_config_path(config_path: Optional[str] = None) -> Path:
    return Path(config_path) if config_path else DEFAULT_CONFIG_PATH


def save_database_path(database_path: str, config_path: Optional[str] = None) -> None:
    path = get_config_path(config_path)
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path, encoding="utf-8-sig")

    if "database" not in parser:
        parser["database"] = {}
    if "app" not in parser:
        parser["app"] = {}
    if "ui" not in parser:
        parser["ui"] = {}

    parser["database"]["path"] = database_path
    parser["database"].setdefault("schema", "sql/mindtask_db_schema.sql")
    parser["app"].setdefault("default_task_limit", "100")
    parser["app"].setdefault("default_search_limit", "20")
    parser["ui"].setdefault("theme", "system")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)


def save_ui_theme(theme: str, config_path: Optional[str] = None) -> None:
    if theme not in {"system", "light", "dark"}:
        raise ValueError("theme must be system, light, or dark")

    path = get_config_path(config_path)
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path, encoding="utf-8-sig")

    if "database" not in parser:
        parser["database"] = {}
    if "app" not in parser:
        parser["app"] = {}
    if "ui" not in parser:
        parser["ui"] = {}

    parser["database"].setdefault("path", "data/mindtask.db")
    parser["database"].setdefault("schema", "sql/mindtask_db_schema.sql")
    parser["app"].setdefault("default_task_limit", "100")
    parser["app"].setdefault("default_search_limit", "20")
    parser["ui"]["theme"] = theme

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
