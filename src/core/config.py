"""Configuration loading for MindTask."""

from __future__ import annotations

import configparser
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_TEMPLATE_PATH = PROJECT_ROOT / "config" / "mindtask.ini.template"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "sql" / "mindtask_db_schema.sql"
APP_NAME = "MindTask"
DEFAULT_UI_SHORTCUTS = {
    "open_tasks": "Ctrl+1",
    "open_settings": "Ctrl+2",
    "open_projects": "Ctrl+P",
    "new_task": "Ctrl+N",
    "focus_search": "Ctrl+F",
    "escape_tasks": "Esc",
    "refresh": "F5",
    "history": "Ctrl+H",
    "save_task": "Ctrl+S",
    "complete_task": "Ctrl+Enter",
    "delete_task": "Ctrl+R",
    "previous_page": "Ctrl+Left",
    "next_page": "Ctrl+Right",
}


@dataclass(frozen=True)
class MindTaskConfig:
    database_path: str
    schema_path: str
    ui_theme: str = "system"
    ui_language: str = "en"
    smart_task_sorting: bool = True
    hide_completed_tasks: bool = False
    ui_shortcuts: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_UI_SHORTCUTS))


def resolve_project_path(value: str) -> str:
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    if not path.is_absolute():
        path = get_application_root() / path
    return str(path)


def get_application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_local_config_path() -> Path:
    return get_application_root() / "config" / "mindtask.ini"


def get_user_config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / ".mindtask"


def get_user_config_path() -> Path:
    return get_user_config_dir() / "mindtask.ini"


def get_default_database_path() -> Path:
    return get_user_config_dir() / "mindtask.db"


def find_config_path(config_path: Optional[str] = None) -> Optional[Path]:
    if config_path:
        path = Path(config_path)
        return path if path.exists() else None

    for path in (get_local_config_path(), get_user_config_path()):
        if path.exists():
            return path
    return None


def load_config(config_path: Optional[str] = None) -> MindTaskConfig:
    path = ensure_config_exists(config_path)
    parser = configparser.ConfigParser()

    parser.read(path, encoding="utf-8-sig")

    database_path = parser.get("database", "path", fallback="data/mindtask.db")
    ui_theme = parser.get("ui", "theme", fallback="system")
    if ui_theme not in {"system", "light", "dark"}:
        ui_theme = "system"
    ui_language = parser.get("ui", "language", fallback="en")
    if ui_language not in {"en", "zh"}:
        ui_language = "en"
    smart_task_sorting = parser.getboolean("ui", "smart_task_sorting", fallback=True)
    hide_completed_tasks = parser.getboolean("ui", "hide_completed_tasks", fallback=False)
    ui_shortcuts = {
        action: parser.get("shortcuts", action, fallback=default_sequence).strip()
        for action, default_sequence in DEFAULT_UI_SHORTCUTS.items()
    }

    return MindTaskConfig(
        database_path=resolve_project_path(database_path),
        schema_path=str(DEFAULT_SCHEMA_PATH),
        ui_theme=ui_theme,
        ui_language=ui_language,
        smart_task_sorting=smart_task_sorting,
        hide_completed_tasks=hide_completed_tasks,
        ui_shortcuts=ui_shortcuts,
    )


def _read_writable_config(config_path: Optional[str] = None) -> tuple[Path, configparser.ConfigParser]:
    path = ensure_config_exists(config_path)
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path, encoding="utf-8-sig")

    if "database" not in parser:
        parser["database"] = {}
    if "ui" not in parser:
        parser["ui"] = {}
    if "shortcuts" not in parser:
        parser["shortcuts"] = {}

    parser["database"].setdefault("path", "data/mindtask.db")
    parser["database"].pop("schema", None)
    if "app" in parser:
        parser.remove_section("app")
    parser["ui"].setdefault("theme", "system")
    parser["ui"].setdefault("language", "en")
    parser["ui"].setdefault("smart_task_sorting", "true")
    parser["ui"].setdefault("hide_completed_tasks", "false")
    parser["ui"].pop("due_day_end", None)
    for action in list(parser["shortcuts"]):
        if action not in DEFAULT_UI_SHORTCUTS:
            parser["shortcuts"].pop(action, None)
    for action, sequence in DEFAULT_UI_SHORTCUTS.items():
        parser["shortcuts"].setdefault(action, sequence)
    return path, parser


def _write_config(path: Path, parser: configparser.ConfigParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)


def get_config_path(config_path: Optional[str] = None) -> Path:
    if config_path:
        return Path(config_path)
    return find_config_path() or get_user_config_path()


def get_config_template_path() -> Path:
    return DEFAULT_CONFIG_TEMPLATE_PATH


def config_exists(config_path: Optional[str] = None) -> bool:
    return find_config_path(config_path) is not None


def ensure_config_exists(config_path: Optional[str] = None) -> Path:
    path = get_config_path(config_path)
    if path.exists():
        return path

    template_path = get_config_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Config file is missing and template was not found: {template_path}")

    create_config_from_template(path)
    return path


def create_config_from_template(config_path: str | Path) -> Path:
    path = Path(config_path)
    if path.exists():
        return path
    template_path = get_config_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Config file is missing and template was not found: {template_path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path, path)

    if path == get_user_config_path():
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8-sig")
        if "database" not in parser:
            parser["database"] = {}
        parser["database"]["path"] = str(get_default_database_path())
        _write_config(path, parser)
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


def save_smart_task_sorting(enabled: bool, config_path: Optional[str] = None) -> None:
    path, parser = _read_writable_config(config_path)
    parser["ui"]["smart_task_sorting"] = "true" if enabled else "false"
    _write_config(path, parser)


def save_hide_completed_tasks(enabled: bool, config_path: Optional[str] = None) -> None:
    path, parser = _read_writable_config(config_path)
    parser["ui"]["hide_completed_tasks"] = "true" if enabled else "false"
    _write_config(path, parser)


def save_ui_shortcuts(shortcuts: Dict[str, str], config_path: Optional[str] = None) -> None:
    path, parser = _read_writable_config(config_path)
    for action in DEFAULT_UI_SHORTCUTS:
        parser["shortcuts"][action] = shortcuts.get(action, "").strip()
    _write_config(path, parser)
