from datetime import datetime
import sqlite3
import time
import json
from contextlib import closing

from src.ai import (
    ACTIONS_JSON_END,
    ACTIONS_JSON_START,
    AIProtocolError,
    AIChatService,
    AIToolExecutor,
    ToolExecutionPolicy,
    assistant_visible_content,
    actions_from_fallback_text,
    actions_from_openai_message,
    date_time_context_prompt,
    system_prompt,
)
from src.core import DatabaseMigrationRequiredError, DatabaseMissingError, MindTaskDB
from src.core.config import ensure_config_exists, load_config, mask_api_key, save_ai_settings, save_hide_completed_tasks
from src.version import __version__
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


def test_database_missing_requires_explicit_create(tmp_path):
    config_path = write_config(tmp_path)
    db_path = tmp_path / "mindtask.db"

    with pytest.raises(DatabaseMissingError):
        MindTaskDB(config_path=config_path)

    assert not db_path.exists()
    MindTaskDB(config_path=config_path, create_if_missing=True)
    assert db_path.exists()
    assert MindTaskDB(config_path=config_path).database_schema_version() == __version__


def test_task_lifecycle(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

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
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
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
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    for index in range(25):
        db.create_task(f"Bulk task {index:02d}")

    assert len(db.get_tasks()) == 25
    assert len(db.search_tasks("Bulk")) == 25
    assert len(db.get_tasks(limit=5)) == 5
    assert len(db.search_tasks("Bulk", limit=5)) == 5


def test_task_timestamps_use_local_time_and_ignore_noop_updates(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

    before_create = datetime.now()
    task_id = db.create_task("Timestamp task")
    created = db.get_task(task_id)
    created_at = datetime.strptime(created["created_at"], "%Y-%m-%d %H:%M:%S")
    updated_at = datetime.strptime(created["updated_at"], "%Y-%m-%d %H:%M:%S")

    assert abs((created_at - before_create).total_seconds()) < 5
    assert abs((updated_at - before_create).total_seconds()) < 5

    assert db.update_task(task_id, title="Timestamp task")
    noop_updated_at = db.get_task(task_id)["updated_at"]
    assert noop_updated_at == created["updated_at"]

    time.sleep(1.1)
    assert db.update_task(task_id, title="Timestamp task updated")
    changed = db.get_task(task_id)
    assert changed["updated_at"] != noop_updated_at
    changed_updated_at = datetime.strptime(changed["updated_at"], "%Y-%m-%d %H:%M:%S")
    assert abs((changed_updated_at - datetime.now()).total_seconds()) < 5


def test_database_initialization_does_not_seed_projects(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

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


def test_ai_config_defaults_and_saves(tmp_path):
    config_path = write_config(tmp_path)

    config = load_config(config_path)
    assert config.ai_base_url == ""
    assert config.ai_api_key == ""
    assert config.ai_models == []
    assert config.ai_allow_database_write is False
    assert config.ai_confirm_delete_actions is True
    assert config.ai_confirm_bulk_actions is True

    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a", "model-b", "model-a", ""],
        models_endpoint="https://example.test/v1/models",
        request_timeout_seconds=45,
        allow_database_write=True,
        confirm_delete_actions=False,
        confirm_bulk_actions=False,
        config_path=config_path,
    )

    saved = load_config(config_path)
    assert saved.ai_base_url == "https://example.test/v1"
    assert saved.ai_api_key == "sk-test-secret"
    assert saved.ai_default_model == "model-a"
    assert saved.ai_models == ["model-a", "model-b"]
    assert saved.ai_models_endpoint == "https://example.test/v1/models"
    assert saved.ai_request_timeout_seconds == 45
    assert saved.ai_allow_database_write is True
    assert saved.ai_confirm_delete_actions is False
    assert saved.ai_confirm_bulk_actions is False

    save_ai_settings(
        base_url="",
        api_key="",
        default_model="",
        models=[],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=False,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    cleared = load_config(config_path)
    assert cleared.ai_api_key == ""
    assert cleared.ai_request_timeout_seconds == 0


def test_api_key_mask_is_display_only():
    assert mask_api_key("") == ""
    assert mask_api_key("short") == "short"
    assert mask_api_key("sk-1234567890") == "sk-1234567890"
    assert mask_api_key("1234567890123456") == "1234567890123456"
    assert mask_api_key("sk-1234567890abcdef") == "sk-12345***90abcdef"


def test_sample_data_is_explicit(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

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
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
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
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    first_id = db.create_task("First task", priority=0, due_date="2026-05-20 10:00:00")
    second_id = db.create_task("Second task", priority=3, due_date="2026-05-10 10:00:00")
    third_id = db.create_task("Third task", priority=1, due_date="2026-05-01 10:00:00")

    assert [task["id"] for task in db.get_tasks()] == [first_id, second_id, third_id]
    assert [task["id"] for task in db.search_tasks("task")] == [first_id, second_id, third_id]


def test_due_date_requires_standard_format(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

    task_id = db.create_task("Due date task", due_date="2026-05-15 18:00:00")
    assert db.get_task(task_id)["due_date"] == "2026-05-15 18:00:00"

    assert db.update_task(task_id, due_date=None)
    assert db.get_task(task_id)["due_date"] is None

    with pytest.raises(ValueError):
        db.create_task("Bad due date", due_date="tomorrow")

    with pytest.raises(ValueError):
        db.update_task(task_id, due_date="2026-05-15")


def test_due_mode_distinguishes_all_day_and_exact_time(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

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
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

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


def test_ai_chat_metadata_is_not_operation_history(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    assert db.get_latest_history_id() is None

    session_id = db.create_ai_chat_session("Planning")
    user_message_id = db.add_ai_chat_message(session_id, "user", "Plan the work")
    db.add_ai_chat_message(session_id, "assistant", "I can help.")

    assert db.get_latest_history_id() is None
    assert len(db.get_ai_chat_sessions()) == 1
    assert [message["role"] for message in db.get_ai_chat_messages(session_id)] == ["user", "assistant"]

    batch_id = db.create_ai_operation_batch(session_id=session_id, user_message_id=user_message_id, model="model-a")
    task_id = db.create_task("AI-created task")
    assert db.complete_ai_operation_batch(batch_id, [{"type": "create_task", "task_id": task_id}])

    batch = db.get_ai_operation_batches(session_id=session_id)[0]
    assert batch["before_history_id"] is None
    assert batch["after_history_id"] == db.get_latest_history_id()
    assert db.delete_ai_chat_session(session_id)
    assert db.get_ai_chat_sessions() == []
    assert db.get_ai_operation_batches()[0]["id"] == batch_id


def test_delete_all_ai_chat_sessions_keeps_batches(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    first = db.create_ai_chat_session("First")
    second = db.create_ai_chat_session("Second")
    batch_id = db.create_ai_operation_batch(session_id=first)

    assert db.delete_all_ai_chat_sessions() == 2
    assert db.get_ai_chat_sessions() == []
    assert db.get_ai_operation_batches()[0]["id"] == batch_id
    assert db.get_ai_operation_batches()[0]["session_id"] is None


def test_ai_protocol_reads_tool_calls_and_fixed_json_block():
    tool_actions = actions_from_openai_message(
        {
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {
                        "name": "create_task",
                        "arguments": '{"title": "From tool call", "priority": 2}',
                    },
                }
            ]
        }
    )
    assert tool_actions == [
        {
            "tool": "create_task",
            "arguments": {"title": "From tool call", "priority": 2},
            "tool_call_id": "call-1",
        }
    ]

    fallback_text = (
        "I will prepare the change.\n"
        f"{ACTIONS_JSON_START}\n"
        '{"actions": [{"tool": "complete_task", "arguments": {"task_id": 12}}]}\n'
        f"{ACTIONS_JSON_END}\n"
        "Done after approval."
    )
    assert actions_from_fallback_text(fallback_text) == [
        {"tool": "complete_task", "arguments": {"task_id": 12}}
    ]
    assert actions_from_fallback_text('{"tool": "delete_task", "arguments": {"task_id": 1}}') == []

    with pytest.raises(AIProtocolError):
        actions_from_fallback_text(f"{ACTIONS_JSON_START} not json {ACTIONS_JSON_END}")


def test_ai_system_prompt_includes_current_time_context():
    prompt = system_prompt()
    context_prompt = date_time_context_prompt(datetime(2026, 5, 24, 19, 30, 0))

    assert "MindTask is a desktop task manager" in prompt
    assert "Now:" not in prompt
    assert "Today:" not in prompt
    assert "MindTask runtime context for the next user message" in context_prompt
    assert "This context applies to the next user message only." in context_prompt
    assert "Now: 2026-05-24 19:30:00" in context_prompt
    assert "Today: 2026-05-24" in context_prompt
    assert "tomorrow" in context_prompt


def test_ai_assistant_visible_content_removes_reasoning():
    message = {
        "reasoning_content": "hidden reasoning",
        "content": "<think>I should not be shown.</think>\nFinal answer.",
    }

    assert assistant_visible_content(message) == "Final answer."
    assert assistant_visible_content({"content": "<thinking>hidden</thinking>Visible"}) == "Visible"
    assert assistant_visible_content({"content": "<think>unfinished"}) == ""
    leaked_text = "MindTask operation result:\n{\"status\":\"ok\"}\nThis text is part of the assistant reply."
    assert assistant_visible_content({"content": leaked_text}) == leaked_text


def test_ai_tool_executor_requires_permission_and_records_batch(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    task_id = db.create_task("Existing")
    executor = AIToolExecutor(db, ToolExecutionPolicy(allow_database_write=False))

    blocked = executor.execute_actions([{"tool": "update_task", "arguments": {"task_id": task_id, "title": "Blocked"}}])
    assert blocked["status"] == "needs_approval"
    assert blocked["reason"] == "brave_mode_off"
    assert db.get_task(task_id)["title"] == "Existing"
    assert db.get_ai_operation_batches() == []

    approved = executor.execute_actions(
        [{"tool": "update_task", "arguments": {"task_id": task_id, "title": "Approved"}}],
        approved=True,
    )
    assert approved["status"] == "ok"
    assert approved["ai_batch_id"] is not None
    assert db.get_task(task_id)["title"] == "Approved"

    history = db.get_history(limit=1)[0]
    assert history["source"] == "ai"
    assert history["ai_batch_id"] == approved["ai_batch_id"]
    batch = db.get_ai_operation_batches()[0]
    assert batch["before_history_id"] is not None
    assert batch["after_history_id"] == history["id"]


def test_ai_tool_executor_requires_permission_for_reads_when_brave_mode_off(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    db.create_task("Readable")
    executor = AIToolExecutor(db, ToolExecutionPolicy(allow_database_write=False))

    blocked = executor.execute_actions([{"tool": "get_tasks", "arguments": {}}])
    assert blocked["status"] == "needs_approval"
    assert blocked["reason"] == "brave_mode_off"

    approved = executor.execute_actions([{"tool": "get_tasks", "arguments": {}}], approved=True)
    assert approved["status"] == "ok"
    assert approved["results"][0]["tool"] == "get_tasks"
    assert approved["results"][0]["result"][0]["title"] == "Readable"


def test_ai_tool_executor_blocks_high_risk_delete_and_bulk(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)
    first_id = db.create_task("First")
    second_id = db.create_task("Second")
    executor = AIToolExecutor(
        db,
        ToolExecutionPolicy(
            allow_database_write=True,
            confirm_delete_actions=True,
            confirm_bulk_actions=True,
        ),
    )

    delete_blocked = executor.execute_actions([{"tool": "delete_task", "arguments": {"task_id": first_id}}])
    assert delete_blocked["status"] == "needs_approval"
    assert delete_blocked["reason"] == "delete_action"
    assert db.get_task(first_id) is not None

    bulk_blocked = executor.execute_actions(
        [
            {"tool": "update_task", "arguments": {"task_id": first_id, "title": "One"}},
            {"tool": "update_task", "arguments": {"task_id": second_id, "title": "Two"}},
        ]
    )
    assert bulk_blocked["status"] == "needs_approval"
    assert bulk_blocked["reason"] == "bulk_action"
    assert db.get_task(first_id)["title"] == "First"

    completed = executor.execute_actions(
        [
            {"tool": "update_task", "arguments": {"task_id": first_id, "title": "One"}},
            {"tool": "update_task", "arguments": {"task_id": second_id, "title": "Two"}},
        ],
        high_risk_approved=True,
    )
    assert completed["status"] == "ok"
    assert db.get_task(first_id)["title"] == "One"
    assert db.get_task(second_id)["title"] == "Two"


def test_ai_chat_service_runs_tool_round_and_stores_messages(tmp_path):
    class FakeAIClient:
        def __init__(self):
            self.calls = 0
            self.seen_messages = []

        def ensure_ready(self, model):
            assert model == "model-a"

        def chat_completion(self, *, model, messages, tools=None):
            self.calls += 1
            self.seen_messages.append(json.loads(json.dumps(messages)))
            if self.calls == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "create_task",
                                "arguments": '{"title": "AI planned task"}',
                            },
                        }
                    ],
                }
            return {"content": "Task created."}

    config_path = write_config(tmp_path)
    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a"],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=True,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    db = MindTaskDB(config_path=config_path, create_if_missing=True)
    fake_client = FakeAIClient()
    service = AIChatService(
        db,
        client=fake_client,
        policy=ToolExecutionPolicy(allow_database_write=True),
    )

    result = service.send_user_message("Create a task")

    assert result.status == "ok"
    assert result.content == "Task created."
    assert fake_client.calls == 2
    second_messages = fake_client.seen_messages[1]
    assert any(
        message["role"] == "system"
        and "Operation results:" in message["content"]
        and "create_task" in message["content"]
        for message in second_messages
    )
    assert db.get_tasks()[0]["title"] == "AI planned task"
    assert len(db.get_ai_operation_batches()) == 1
    assert [message["role"] for message in db.get_ai_chat_messages(result.session_id)] == [
        "system",
        "system",
        "user",
        "assistant",
        "system",
        "assistant",
    ]


def test_ai_chat_service_stores_first_user_message_before_ai_reply(tmp_path):
    class FakeAIClient:
        def __init__(self, db):
            self.db = db

        def ensure_ready(self, model):
            pass

        def chat_completion(self, *, model, messages, tools=None):
            sessions = self.db.get_ai_chat_sessions()
            assert len(sessions) == 1
            stored_messages = self.db.get_ai_chat_messages(sessions[0]["id"])
            assert [message["role"] for message in stored_messages] == ["system", "system", "user"]
            assert stored_messages[-1]["content"] == "Store me first"
            return {"content": "Stored."}

    config_path = write_config(tmp_path)
    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a"],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=True,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    db = MindTaskDB(config_path=config_path, create_if_missing=True)
    result = AIChatService(
        db,
        client=FakeAIClient(db),
        policy=ToolExecutionPolicy(allow_database_write=True),
    ).send_user_message("Store me first")

    assert result.status == "ok"
    assert [message["role"] for message in db.get_ai_chat_messages(result.session_id)] == [
        "system",
        "system",
        "user",
        "assistant",
    ]


def test_ai_chat_service_returns_pending_actions_when_permission_blocks(tmp_path):
    class FakeAIClient:
        def ensure_ready(self, model):
            pass

        def chat_completion(self, *, model, messages, tools=None):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "create_task",
                            "arguments": '{"title": "Needs approval"}',
                        },
                    }
                ],
            }

    config_path = write_config(tmp_path)
    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a"],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=False,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    db = MindTaskDB(config_path=config_path, create_if_missing=True)
    service = AIChatService(
        db,
        client=FakeAIClient(),
        policy=ToolExecutionPolicy(allow_database_write=False),
    )

    result = service.send_user_message("Create a task")

    assert result.status == "needs_approval"
    assert result.pending_actions == [{"tool": "create_task", "arguments": {"title": "Needs approval"}, "tool_call_id": "call-1"}]
    assert db.get_tasks() == []
    assert db.get_ai_operation_batches() == []
    messages = db.get_ai_chat_messages(result.session_id)
    assert [message["role"] for message in messages] == ["system", "system", "user", "assistant"]
    pending = db.get_pending_ai_approval(result.session_id)
    assert pending is not None
    assert pending["id"] == result.assistant_message_id
    assert pending["metadata"]["approval_status"] == "pending"


def test_ai_approval_status_persists_and_clears_pending_state(tmp_path):
    class FakeAIClient:
        def ensure_ready(self, model):
            pass

        def chat_completion(self, *, model, messages, tools=None):
            return {"content": "Done"}

    config_path = write_config(tmp_path)
    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a"],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=False,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    db = MindTaskDB(config_path=config_path, create_if_missing=True)
    session_id = db.create_ai_chat_session("Pending")
    user_message_id = db.add_ai_chat_message(session_id, "user", "Create one")
    assistant_message_id = db.add_ai_chat_message(
        session_id,
        "assistant",
        "Need approval",
        metadata={
            "actions": [{"tool": "create_task", "arguments": {"title": "Approved task"}}],
            "approval_status": "pending",
        },
    )

    AIChatService(
        db,
        client=FakeAIClient(),
        policy=ToolExecutionPolicy(allow_database_write=False),
    ).continue_after_approval(
        session_id=session_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        actions=[{"tool": "create_task", "arguments": {"title": "Approved task"}}],
    )

    assistant = [message for message in db.get_ai_chat_messages(session_id) if message["id"] == assistant_message_id][0]
    assert json.loads(assistant["metadata_json"])["approval_status"] == "approved"
    assert db.get_pending_ai_approval(session_id) is None


def test_ai_allow_once_executes_only_next_pending_action(tmp_path):
    class FakeAIClient:
        def ensure_ready(self, model):
            pass

        def chat_completion(self, *, model, messages, tools=None):
            raise AssertionError("AI should not continue while more approved actions are still pending")

    config_path = write_config(tmp_path)
    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a"],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=False,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    db = MindTaskDB(config_path=config_path, create_if_missing=True)
    first_id = db.create_task("First")
    second_id = db.create_task("Second")
    actions = [
        {"tool": "update_task", "arguments": {"task_id": first_id, "priority": 2}},
        {"tool": "update_task", "arguments": {"task_id": second_id, "priority": 3}},
    ]
    session_id = db.create_ai_chat_session("Pending")
    user_message_id = db.add_ai_chat_message(session_id, "user", "Update two tasks")
    assistant_message_id = db.add_ai_chat_message(
        session_id,
        "assistant",
        "",
        metadata={"actions": actions, "approval_status": "pending"},
    )

    result = AIChatService(
        db,
        client=FakeAIClient(),
        policy=ToolExecutionPolicy(allow_database_write=False),
    ).continue_after_approval(
        session_id=session_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        actions=actions,
        allow_follow_up_actions=False,
    )

    assert result.status == "needs_approval"
    assert result.pending_actions == [actions[1]]
    assert db.get_task(first_id)["priority"] == 2
    assert db.get_task(second_id)["priority"] == 0
    assistant = [message for message in db.get_ai_chat_messages(session_id) if message["id"] == assistant_message_id][0]
    metadata = json.loads(assistant["metadata_json"])
    assert metadata["approval_status"] == "pending"
    assert [item["status"] for item in metadata["action_results"]] == ["ok", "pending"]


def test_ai_approval_failure_records_action_result(tmp_path):
    class FakeAIClient:
        def __init__(self):
            self.seen_messages = []

        def ensure_ready(self, model):
            pass

        def chat_completion(self, *, model, messages, tools=None):
            self.seen_messages.append(json.loads(json.dumps(messages)))
            return {"content": "The task was not created because the due date format was invalid."}

    config_path = write_config(tmp_path)
    save_ai_settings(
        base_url="https://example.test/v1",
        api_key="sk-test-secret",
        default_model="model-a",
        models=["model-a"],
        models_endpoint="",
        request_timeout_seconds=0,
        allow_database_write=False,
        confirm_delete_actions=True,
        confirm_bulk_actions=True,
        config_path=config_path,
    )
    db = MindTaskDB(config_path=config_path, create_if_missing=True)
    action = {
        "tool": "create_task",
        "arguments": {
            "title": "example",
            "description": "新创建的任务",
            "due_date": "2026-05-25",
            "priority": 3,
            "status": 0,
        },
    }
    session_id = db.create_ai_chat_session("Pending")
    user_message_id = db.add_ai_chat_message(session_id, "user", "Create one")
    assistant_message_id = db.add_ai_chat_message(
        session_id,
        "assistant",
        "",
        metadata={"actions": [action], "approval_status": "pending"},
    )

    fake_client = FakeAIClient()
    result = AIChatService(
        db,
        client=fake_client,
        policy=ToolExecutionPolicy(allow_database_write=False),
    ).continue_after_approval(
        session_id=session_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        actions=[action],
    )

    assert result.status == "ok"
    assert "not created" in result.content
    assert any(
        message["role"] == "system"
        and "operation #1 failed" in message["content"]
        for message in fake_client.seen_messages[0]
    )
    assistant = [message for message in db.get_ai_chat_messages(session_id) if message["id"] == assistant_message_id][0]
    metadata = json.loads(assistant["metadata_json"])
    assert metadata["approval_status"] == "failed"
    assert metadata["action_results"][0]["status"] == "error"
    assert metadata["action_results"][0]["result_type"] == "error"
    assert "YYYY-MM-DD HH:MM:SS" in metadata["action_results"][0]["result"]
    assert db.get_pending_ai_approval(session_id) is None


def test_old_database_migrates_ai_metadata_columns(tmp_path):
    config_path = write_config(tmp_path)
    db_path = tmp_path / "mindtask.db"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                color TEXT DEFAULT '#007BFF',
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                project_id INTEGER,
                priority INTEGER DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
                status INTEGER DEFAULT 0 CHECK (status BETWEEN 0 AND 3),
                due_date TIMESTAMP,
                due_mode TEXT DEFAULT 'none',
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE operation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                before_json TEXT,
                after_json TEXT,
                undone_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE VIEW task_details AS
            SELECT
                t.id,
                t.title,
                t.description,
                t.project_id,
                p.name AS project_name,
                p.color AS project_color,
                t.priority,
                'None' AS priority_text,
                t.status,
                'not_started' AS status_text,
                t.due_date,
                t.due_mode,
                t.completed_at,
                t.created_at,
                t.updated_at
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id;
            """
        )

    with pytest.raises(DatabaseMigrationRequiredError):
        MindTaskDB(config_path=config_path)

    db = MindTaskDB(config_path=config_path, migrate_if_needed=True)
    task_id = db.create_task("Migrated AI metadata")
    batch_id = db.create_ai_operation_batch(model="model-a")
    assert db.complete_ai_operation_batch(batch_id, [{"type": "create_task", "task_id": task_id}])

    with closing(sqlite3.connect(db_path)) as conn:
        history_columns = {row[1] for row in conn.execute("PRAGMA table_info(operation_history)").fetchall()}
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    assert {"source", "ai_batch_id"}.issubset(history_columns)
    assert {"ai_chat_sessions", "ai_chat_messages", "ai_operation_batches"}.issubset(tables)


def test_undo_operations_until_selected_history(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

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


def test_undo_ai_operation_batch_returns_to_before_batch(tmp_path):
    db = MindTaskDB(config_path=write_config(tmp_path), create_if_missing=True)

    keep_id = db.create_task("Keep")
    batch_id = db.create_ai_operation_batch(model="model-a")
    first_ai_id = db.create_task("AI one", source="ai", ai_batch_id=batch_id)
    second_ai_id = db.create_task("AI two", source="ai", ai_batch_id=batch_id)
    assert db.complete_ai_operation_batch(batch_id, [{"type": "create_task", "task_id": first_ai_id}])
    later_id = db.create_task("Later user task")

    undone = db.undo_ai_operation_batch(batch_id)

    assert [row["entity_id"] for row in undone] == [later_id, second_ai_id, first_ai_id]
    assert db.get_task(keep_id) is not None
    assert db.get_task(first_ai_id) is None
    assert db.get_task(second_ai_id) is None
    assert db.get_task(later_id) is None
    assert db.get_ai_operation_batches()[0]["undone_at"]
    assert db.undo_ai_operation_batch(batch_id) == []
