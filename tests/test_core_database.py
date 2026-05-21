from src.core import MindTaskDB
from src.core.config import ensure_config_exists, load_config, save_hide_completed_tasks
import pytest


def write_config(tmp_path):
    config_path = tmp_path / "mindtask.ini"
    db_path = tmp_path / "mindtask.db"
    config_path.write_text(
        f"""
[database]
path = {db_path}
""".strip(),
        encoding="utf-8",
    )
    return str(config_path)


def test_task_lifecycle(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    project_id = db.create_project("Test Project")
    task_id = db.create_task(
        "Write tests",
        description="Cover the core task flow",
        project_id=project_id,
        priority=3,
    )

    task = db.get_task(task_id)
    assert task is not None
    assert task["title"] == "Write tests"
    assert task["project_name"] == "Test Project"
    assert task["priority_text"] == "High"

    assert db.update_task(task_id, status=1)
    assert db.get_task(task_id)["status_text"] == "in_progress"

    assert db.update_task(task_id, status=2)
    assert db.get_task(task_id)["status_text"] == "suspended"

    assert db.complete_task(task_id)
    completed = db.get_task(task_id)
    assert completed["status"] == 3
    assert completed["status_text"] == "completed"
    assert completed["completed_at"] is not None

    assert db.delete_task(task_id)
    assert db.get_task(task_id) is None


def test_search_and_stats(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))
    db.create_task("Alpha task", priority=1)
    db.create_task("Beta task", priority=2)

    results = db.search_tasks("Alpha")
    assert len(results) == 1
    assert results[0]["title"] == "Alpha task"

    stats = db.get_stats()
    assert stats["total_tasks"] == 2
    assert stats["not_started_tasks"] == 2
    assert stats["in_progress_tasks"] == 0
    assert stats["suspended_tasks"] == 0
    assert stats["pending_tasks"] == 2


def test_task_list_and_search_are_unlimited_by_default(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))
    for index in range(25):
        db.create_task(f"Bulk task {index:02d}")

    assert len(db.get_tasks()) == 25
    assert len(db.search_tasks("Bulk")) == 25
    assert len(db.get_tasks(limit=5)) == 5
    assert len(db.search_tasks("Bulk", limit=5)) == 5


def test_database_initialization_does_not_seed_projects(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    assert db.get_projects() == []


def test_missing_config_is_created_from_template(tmp_path, monkeypatch):
    template_path = tmp_path / "mindtask.ini.template"
    config_path = tmp_path / "mindtask.ini"
    db_path = tmp_path / "mindtask.db"
    template_path.write_text(
        f"""
[database]
path = {db_path}

[ui]
theme = dark
language = zh

[shortcuts]
delete_task = Ctrl+D
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.core.config.DEFAULT_CONFIG_TEMPLATE_PATH", template_path)

    created_path = ensure_config_exists(str(config_path))
    config = load_config(str(config_path))

    assert created_path == config_path
    assert config_path.exists()
    assert config.ui_theme == "dark"
    assert config.ui_language == "zh"
    assert config.ui_shortcuts["delete_task"] == "Ctrl+D"
    assert config.ui_shortcuts["refresh"] == "F5"


def test_missing_config_requires_template(tmp_path, monkeypatch):
    config_path = tmp_path / "mindtask.ini"
    monkeypatch.setattr("src.core.config.DEFAULT_CONFIG_TEMPLATE_PATH", tmp_path / "missing.template")

    with pytest.raises(FileNotFoundError):
        ensure_config_exists(str(config_path))


def test_hide_completed_tasks_config_defaults_and_saves(tmp_path):
    config_path = write_config(tmp_path)

    assert load_config(config_path).hide_completed_tasks is False

    save_hide_completed_tasks(True, config_path)

    assert load_config(config_path).hide_completed_tasks is True


def test_sample_data_is_explicit(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    sample = db.create_sample_data()

    assert len(sample["project_ids"]) == 2
    assert len(sample["task_ids"]) == 3
    assert [project["name"] for project in db.get_projects()] == ["Work", "Personal"]
    assert [task["title"] for task in db.get_tasks()] == [
        "Review MindTask",
        "Plan next tasks",
        "Try history undo",
    ]


def test_project_management_summaries_and_empty_delete(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))
    project_id = db.create_project("Managed")
    empty_project_id = db.create_project("Empty")
    task_id = db.create_task("Project task", project_id=project_id, status=1)
    completed_id = db.create_task("Done task", project_id=project_id, status=3)

    assert [project["id"] for project in db.get_projects()][-2:] == [project_id, empty_project_id]
    assert [project["id"] for project in db.get_project_summaries()][-2:] == [project_id, empty_project_id]

    summaries = {project["name"]: project for project in db.get_project_summaries()}
    assert summaries["Managed"]["task_count"] == 2
    assert summaries["Managed"]["active_task_count"] == 1
    assert summaries["Managed"]["completed_task_count"] == 1
    assert summaries["Empty"]["task_count"] == 0

    assert db.update_project(project_id, name="Renamed")
    assert db.get_task(task_id)["project_name"] == "Renamed"
    assert db.get_task(completed_id)["project_name"] == "Renamed"

    with pytest.raises(ValueError):
        db.delete_project(project_id)
    assert db.get_project(project_id) is not None

    assert db.delete_project(empty_project_id)
    assert db.get_project(empty_project_id) is None


def test_tasks_are_listed_by_id_by_default(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))
    first_id = db.create_task("First task", priority=0, due_date="2026-05-20 10:00:00")
    second_id = db.create_task("Second task", priority=3, due_date="2026-05-10 10:00:00")
    third_id = db.create_task("Third task", priority=1, due_date="2026-05-01 10:00:00")

    assert [task["id"] for task in db.get_tasks()] == [first_id, second_id, third_id]
    assert [task["id"] for task in db.search_tasks("task")] == [first_id, second_id, third_id]


def test_due_date_requires_standard_format(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    task_id = db.create_task("Due date task", due_date="2026-05-15 18:00:00")
    assert db.get_task(task_id)["due_date"] == "2026-05-15 18:00:00"

    assert db.update_task(task_id, due_date=None)
    assert db.get_task(task_id)["due_date"] is None

    with pytest.raises(ValueError):
        db.create_task("Bad due date", due_date="tomorrow")

    with pytest.raises(ValueError):
        db.update_task(task_id, due_date="2026-05-15")


def test_due_mode_distinguishes_all_day_and_exact_time(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    all_day_id = db.create_task("All day", due_date="2026-05-14 18:30:00", due_mode="all_day")
    exact_id = db.create_task("Exact", due_date="2026-05-14 18:30:00", due_mode="exact_time")
    none_id = db.create_task("No due", due_date="2026-05-14 18:30:00", due_mode="none")

    all_day = db.get_task(all_day_id)
    assert all_day["due_mode"] == "all_day"
    assert all_day["due_date"] == "2026-05-14 00:00:00"

    exact = db.get_task(exact_id)
    assert exact["due_mode"] == "exact_time"
    assert exact["due_date"] == "2026-05-14 18:30:00"

    no_due = db.get_task(none_id)
    assert no_due["due_mode"] == "none"
    assert no_due["due_date"] is None


def test_history_and_undo_create_update_delete(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    task_id = db.create_task("History task", priority=1)
    assert db.get_task(task_id) is not None
    assert db.get_history(limit=1)[0]["action"] == "create"

    undone = db.undo_last_operation()
    assert undone["action"] == "create"
    assert db.get_task(task_id) is None

    task_id = db.create_task("History task", priority=1)
    assert db.update_task(task_id, title="Updated history task", priority=3)
    assert db.get_task(task_id)["title"] == "Updated history task"

    undone = db.undo_last_operation()
    assert undone["action"] == "update"
    restored = db.get_task(task_id)
    assert restored["title"] == "History task"
    assert restored["priority_text"] == "Low"

    assert db.delete_task(task_id)
    assert db.get_task(task_id) is None
    undone = db.undo_last_operation()
    assert undone["action"] == "delete"
    assert db.get_task(task_id)["title"] == "History task"


def test_undo_operations_until_selected_history(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path))

    first_id = db.create_task("First")
    second_id = db.create_task("Second")
    third_id = db.create_task("Third")
    history_rows = db.get_history(limit=3)
    target_history_id = next(row["id"] for row in history_rows if row["entity_id"] == second_id)

    undone = db.undo_operations_until(target_history_id)

    assert [row["entity_id"] for row in undone] == [third_id, second_id]
    assert db.get_task(first_id) is not None
    assert db.get_task(second_id) is None
    assert db.get_task(third_id) is None
