# MindTask

MindTask is a small SQLite-backed task manager with three entry points:

- CLI commands for scripts and daily use
- A simple JSON-RPC server for MCP-style integrations
- A PySide6 desktop UI for daily use

MindTask is developed with assistance from Codex.

## Project Layout

```text
MindTask/
  src/
    core/      Database access and business logic
    cli/       Command-line entry point
    mcp/       JSON-RPC tool wrappers
    ui/        PySide6 desktop UI
  sql/         SQLite schema
  data/        Local SQLite database files
  docs/        Quickstart, CLI, and MCP docs
```

## Usage

```bash
python MindTask_cli.py --help
python MindTask_cli.py projects
python MindTask_cli.py project-add Work --description "Work tasks"
python MindTask_cli.py add "Write report" --priority high --due "2026-05-15 18:00:00"
python MindTask_cli.py list --detailed
python MindTask_cli.py update 1 --status in_progress
python MindTask_cli.py complete 1
python MindTask_cli.py history
python MindTask_cli.py undo
python MindTask_cli.py version
python MindTask_cli.py stats
```

JSON-RPC server self-test:

```bash
python MindTask_mcp.py
python -m src.mcp.server --test
```

Desktop UI:

```bash
pip install -e .[ui]
python MindTask_ui.py
```

## Configuration

Default settings live in `config/mindtask.ini.template`.
MindTask creates `config/mindtask.ini` from that template the first time it runs:

```ini
[database]
path = data/mindtask.db

[app]
default_task_limit = 100
default_search_limit = 20

[ui]
theme = system
language = en
```

Relative paths are resolved from the project root. Use `--config path/to/file.ini` to run with another config file. If that config file does not exist, MindTask copies it from `config/mindtask.ini.template`. If the template is missing, startup fails with an error.

## Development

Install in editable mode:

```bash
pip install -e .[dev]
```

Run tests when Python and pytest are available:

```bash
pytest
```

## More Docs

- `docs/index.md`
- `docs/quickstart.md`
- `docs/cli-reference.md`
- `docs/mcp-integration.md`
- `docs/desktop-ui.md`
- `docs/iteration-log.md`

The iteration log is maintained by version. Update it immediately before creating a release commit, not after every local change.

## Notes

- The default database is `data/mindtask.db`.
- Tables and views are initialized automatically from `sql/mindtask_db_schema.sql`.
- Task status values are `0 not_started`, `1 in_progress`, `2 suspended`, and `3 completed`.
- Write operations are recorded in `operation_history`; use `history` and `undo` to inspect and roll back the latest operation.
- Local database files and cache folders are ignored by git.
