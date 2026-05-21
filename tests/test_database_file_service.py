import sqlite3
from contextlib import closing

import pytest

from src.core import MindTaskDB
from src.ui.settings.database_file_service import DatabaseFileService, DatabasePathError


def write_config(tmp_path, db_path=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "mindtask.ini"
    db_path = db_path or tmp_path / "mindtask.db"
    config_path.write_text(
        f"""
[database]
path = {db_path}

[ui]
theme = light
language = en
smart_task_sorting = true
hide_completed_tasks = false
""".strip(),
        encoding="utf-8",
    )
    return config_path


def assert_service_error(key, func, *args, **kwargs):
    with pytest.raises(DatabasePathError) as exc_info:
        func(*args, **kwargs)
    assert exc_info.value.key == key


def test_create_and_open_existing_database(tmp_path):
    config_path = write_config(tmp_path)
    service = DatabaseFileService(str(config_path), language="zh")
    database_path = tmp_path / "created.sqlite3"

    created_db = service.create_database(str(database_path), with_sample_data=False)
    assert created_db.db_path == str(database_path)
    assert database_path.exists()

    opened_db = service.open_existing_database(str(database_path))
    assert opened_db.db_path == str(database_path)
    assert opened_db.get_tasks(limit=1) == []


def test_database_paths_must_be_absolute_and_use_sqlite_suffix(tmp_path):
    service = DatabaseFileService(str(write_config(tmp_path)))

    assert_service_error("database_path_must_be_absolute", service.inspect_new_database_target, "relative.db")
    assert_service_error("database_extension_required", service.inspect_new_database_target, str(tmp_path / "data.txt"))


def test_open_existing_database_rejects_missing_empty_and_non_sqlite_files(tmp_path):
    service = DatabaseFileService(str(write_config(tmp_path)))
    empty_path = tmp_path / "empty.db"
    empty_path.touch()
    text_path = tmp_path / "text.db"
    text_path.write_text("not sqlite", encoding="utf-8")

    assert_service_error("database_file_not_found", service.open_existing_database, str(tmp_path / "missing.db"))
    assert_service_error("database_file_empty", service.open_existing_database, str(empty_path))
    assert_service_error("invalid_sqlite_database", service.open_existing_database, str(text_path))


def test_open_existing_database_requires_mindtask_schema(tmp_path):
    service = DatabaseFileService(str(write_config(tmp_path)))
    sqlite_path = tmp_path / "plain.db"
    with closing(sqlite3.connect(sqlite_path)) as conn:
        conn.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
        conn.commit()

    assert_service_error("not_mindtask_database", service.open_existing_database, str(sqlite_path))


def test_inspect_and_create_database_handle_existing_targets(tmp_path):
    service = DatabaseFileService(str(write_config(tmp_path)))
    database_path = tmp_path / "target.db"
    database_path.write_text("old content", encoding="utf-8")

    target = service.inspect_new_database_target(str(database_path))
    assert target.path == database_path
    assert target.exists is True
    assert_service_error("database_file_exists", service.create_database, str(database_path), overwrite=False)

    db = service.create_database(str(database_path), overwrite=True, with_sample_data=False)
    assert db.db_path == str(database_path)
    assert service.open_existing_database(str(database_path)).get_tasks(limit=1) == []


def test_backup_database_copies_valid_database(tmp_path):
    config_path = write_config(tmp_path)
    source_db = MindTaskDB(config_path=str(config_path))
    task_id = source_db.create_task("Backup me")
    service = DatabaseFileService(str(config_path))
    backup_path = tmp_path / "backup.sqlite"

    copied_path = service.backup_database(source_db.db_path, str(backup_path))
    assert copied_path == backup_path

    backup_config_path = write_config(tmp_path / "backup-config", db_path=backup_path)
    backup_db = MindTaskDB(config_path=str(backup_config_path))
    assert backup_db.get_task(task_id)["title"] == "Backup me"
