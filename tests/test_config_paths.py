import configparser
from pathlib import Path

from src.core import config


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
[database]
path = data/mindtask.db

[ui]
theme = system
language = en
smart_task_sorting = true
hide_completed_tasks = false
""".strip(),
        encoding="utf-8",
    )


def set_config_roots(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path / "app"
    template_path = project_root / "config" / "mindtask.ini.template"
    write_template(template_path)
    monkeypatch.setattr(config, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(config, "DEFAULT_CONFIG_TEMPLATE_PATH", template_path)
    monkeypatch.setattr(config, "DEFAULT_SCHEMA_PATH", project_root / "sql" / "mindtask_db_schema.sql")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return project_root, tmp_path / "appdata" / "MindTask"


def test_config_lookup_prefers_explicit_then_local_then_user(monkeypatch, tmp_path):
    project_root, user_dir = set_config_roots(monkeypatch, tmp_path)
    local_config = project_root / "config" / "mindtask.ini"
    user_config = user_dir / "mindtask.ini"
    explicit_config = tmp_path / "custom.ini"
    for path in (local_config, user_config, explicit_config):
        write_template(path)

    assert config.find_config_path(str(explicit_config)) == explicit_config
    assert config.find_config_path() == local_config
    local_config.unlink()
    assert config.find_config_path() == user_config


def test_missing_explicit_config_is_not_created(monkeypatch, tmp_path):
    set_config_roots(monkeypatch, tmp_path)
    missing = tmp_path / "missing.ini"

    assert config.find_config_path(str(missing)) is None
    assert not missing.exists()


def test_ensure_config_creates_user_config_with_absolute_database_path(monkeypatch, tmp_path):
    _, user_dir = set_config_roots(monkeypatch, tmp_path)

    created = config.ensure_config_exists()

    assert created == user_dir / "mindtask.ini"
    parser = configparser.ConfigParser()
    parser.read(created, encoding="utf-8")
    database_path = Path(parser["database"]["path"])
    assert database_path.is_absolute()
    assert database_path == user_dir / "mindtask.db"
