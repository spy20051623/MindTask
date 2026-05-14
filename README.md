# MindTask

MindTask is a small SQLite-backed task manager with three entry points:

- CLI commands for scripts and daily use
- An interactive shell
- A simple JSON-RPC server for MCP-style integrations

## Project Layout

```text
MindTask/
  src/
    core/      Database access and business logic
    cli/       Command-line and interactive shell entry points
    mcp/       JSON-RPC tool wrappers
  sql/         SQLite schema
  data/        Local SQLite database files
  docs/        Quickstart, CLI, and MCP docs
```

## Usage

```bash
python MindTask_cli.py --help
python MindTask_cli.py projects
python MindTask_cli.py project-add Work --description "Work tasks"
python MindTask_cli.py add "Write report" --priority high --due tomorrow
python MindTask_cli.py list --detailed
python MindTask_cli.py complete 1
python MindTask_cli.py history
python MindTask_cli.py undo
python MindTask_cli.py version
python MindTask_cli.py stats
```

Interactive shell:

```bash
python MindTask_shell.py
```

JSON-RPC server self-test:

```bash
python MindTask_mcp.py
python -m src.mcp.server --test
```

## Configuration

Fixed settings live in `config/mindtask.ini`:

```ini
[database]
path = data/mindtask.db
schema = sql/mindtask_db_schema.sql

[app]
default_task_limit = 100
default_search_limit = 20
```

Relative paths are resolved from the project root. Use `--config path/to/file.ini` to run with another config file. The database path is read only from the active config file.

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
- `docs/iteration-log.md`

The iteration log is maintained by version. Update it immediately before creating a release commit, not after every local change.

## Notes

- The default database is `data/mindtask.db`.
- Tables and views are initialized automatically from `sql/mindtask_db_schema.sql`.
- Write operations are recorded in `operation_history`; use `history` and `undo` to inspect and roll back the latest operation.
- Local database files and cache folders are ignored by git.
