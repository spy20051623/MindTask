from src.mcp.tools import MindTaskMCPTools


def write_config(tmp_path):
    config_path = tmp_path / "mindtask.ini"
    db_path = tmp_path / "mindtask.db"
    config_path.write_text(
        f"""
[database]
path = {db_path}
schema = sql/mindtask_db_schema.sql

[app]
default_task_limit = 100
default_search_limit = 20
""".strip(),
        encoding="utf-8",
    )
    return str(config_path)


def test_mcp_create_and_get_task(tmp_path):
    tools = MindTaskMCPTools(config_path=write_config(tmp_path))

    created = tools.create_task("MCP task", priority=2)
    assert created["success"] is True
    task_id = created["task_id"]

    fetched = tools.get_task(task_id)
    assert fetched["success"] is True
    assert fetched["data"]["title"] == "MCP task"

    completed = tools.complete_task(task_id)
    assert completed["success"] is True
    assert completed["data"]["status_text"] == "Done"


def test_mcp_history_and_undo(tmp_path):
    tools = MindTaskMCPTools(config_path=write_config(tmp_path))
    created = tools.create_task("Undo through MCP")
    task_id = created["task_id"]

    history = tools.get_history(limit=1)
    assert history["success"] is True
    assert history["data"][0]["action"] == "create"

    undone = tools.undo_last_operation()
    assert undone["success"] is True
    assert tools.get_task(task_id)["success"] is False
