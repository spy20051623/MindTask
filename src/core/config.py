"""Configuration loading for MindTask."""

from __future__ import annotations

import configparser
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "mindtask.ini"
DEFAULT_CONFIG_TEMPLATE_PATH = PROJECT_ROOT / "config" / "mindtask.ini.template"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "sql" / "mindtask_db_schema.sql"
DEFAULT_UI_SHORTCUTS = {
    "open_tasks": "Ctrl+1",
    "open_projects": "Ctrl+2",
    "open_settings": "Ctrl+3",
    "new_task": "Ctrl+N",
    "focus_search": "Ctrl+F",
    "escape_tasks": "Esc",
    "refresh": "F5",
    "undo": "Ctrl+U",
    "history": "Ctrl+H",
    "save_task": "Ctrl+S",
    "complete_task": "Ctrl+Enter",
    "delete_task": "Ctrl+R",
}


@dataclass(frozen=True)
class MindTaskConfig:
    database_path: str
    schema_path: str
    default_task_limit: int = 100
    default_search_limit: int = 20
    ui_theme: str = "system"
    ui_language: str = "en"
    ui_due_day_end: str = "same_day"
    ui_shortcuts: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_UI_SHORTCUTS))


def resolve_project_path(value: str) -> str:
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def load_config(config_path: Optional[str] = None) -> MindTaskConfig:
    path = ensure_config_exists(config_path)
    parser = configparser.ConfigParser()

    parser.read(path, encoding="utf-8-sig")

    database_path = parser.get("database", "path", fallback="data/mindtask.db")
    default_task_limit = parser.getint("app", "default_task_limit", fallback=100)
    default_search_limit = parser.getint("app", "default_search_limit", fallback=20)
    ui_theme = parser.get("ui", "theme", fallback="system")
    if ui_theme not in {"system", "light", "dark"}:
        ui_theme = "system"
    ui_language = parser.get("ui", "language", fallback="en")
    if ui_language not in {"en", "zh"}:
        ui_language = "en"
    ui_due_day_end = parser.get("ui", "due_day_end", fallback="same_day")
    if ui_due_day_end not in {"same_day", "next_day_early_morning"}:
        ui_due_day_end = "same_day"
    ui_shortcuts = {
        action: parser.get("shortcuts", action, fallback=default_sequence).strip()
        for action, default_sequence in DEFAULT_UI_SHORTCUTS.items()
    }

    return MindTaskConfig(
        database_path=resolve_project_path(database_path),
        schema_path=str(DEFAULT_SCHEMA_PATH),
        default_task_limit=default_task_limit,
        default_search_limit=default_search_limit,
        ui_theme=ui_theme,
        ui_language=ui_language,
        ui_due_day_end=ui_due_day_end,
        ui_shortcuts=ui_shortcuts,
    )


def _read_writable_config(config_path: Optional[str] = None) -> tuple[Path, configparser.ConfigParser]:
    path = ensure_config_exists(config_path)
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path, encoding="utf-8-sig")

    if "database" not in parser:
        parser["database"] = {}
    if "app" not in parser:
        parser["app"] = {}
    if "ui" not in parser:
        parser["ui"] = {}
    if "shortcuts" not in parser:
        parser["shortcuts"] = {}

    parser["database"].setdefault("path", "data/mindtask.db")
    parser["database"].pop("schema", None)
    parser["app"].setdefault("default_task_limit", "100")
    parser["app"].setdefault("default_search_limit", "20")
    parser["ui"].setdefault("theme", "system")
    parser["ui"].setdefault("language", "en")
    parser["ui"].setdefault("due_day_end", "same_day")
    for action, sequence in DEFAULT_UI_SHORTCUTS.items():
        parser["shortcuts"].setdefault(action, sequence)
    return path, parser


def _write_config(path: Path, parser: configparser.ConfigParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)


def get_config_path(config_path: Optional[str] = None) -> Path:
    return Path(config_path) if config_path else DEFAULT_CONFIG_PATH


def get_config_template_path() -> Path:
    return DEFAULT_CONFIG_TEMPLATE_PATH


def config_exists(config_path: Optional[str] = None) -> bool:
    return get_config_path(config_path).exists()


def ensure_config_exists(config_path: Optional[str] = None) -> Path:
    path = get_config_path(config_path)
    if path.exists():
        return path

    template_path = get_config_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Config file is missing and template was not found: {template_path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path, path)
    return path


def save_database_path(database_path: str, config_path: Optional[str] = None) -> None:
    path, parser = _read_writable_config(config_path)
    parser["database"]["path"] = database_path
    _write_config(path, parser)


def save_ui_theme(theme: str, config_path: Optional[str] = None) -> None:
    if theme not in {"system", "light", "dark"}:
        raise ValueError("theme must be system, light, or dark")

    path, parser = _read_writable_config(config_path)
    parser["ui"]["theme"] = theme
    _write_config(path, parser)


def save_ui_language(language: str, config_path: Optional[str] = None) -> None:
    if language not in {"en", "zh"}:
        raise ValueError("language must be en or zh")

    path, parser = _read_writable_config(config_path)
    parser["ui"]["language"] = language
    _write_config(path, parser)


def save_ui_due_day_end(value: str, config_path: Optional[str] = None) -> None:
    if value not in {"same_day", "next_day_early_morning"}:
        raise ValueError("due day end must be same_day or next_day_early_morning")

    path, parser = _read_writable_config(config_path)
    parser["ui"]["due_day_end"] = value
    _write_config(path, parser)


def save_ui_shortcuts(shortcuts: Dict[str, str], config_path: Optional[str] = None) -> None:
    path, parser = _read_writable_config(config_path)
    for action in DEFAULT_UI_SHORTCUTS:
        parser["shortcuts"][action] = shortcuts.get(action, "").strip()
    _write_config(path, parser)
