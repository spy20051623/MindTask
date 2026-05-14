# Quickstart

## 1. Check Configuration

MindTask reads fixed settings from `config/mindtask.ini`.

```ini
[database]
path = data/mindtask.db
schema = sql/mindtask_db_schema.sql
```

## 2. Initialize The Database

```bash
python scripts/setup_MindTask_db.py
```

## 3. Create And List Tasks

```bash
python MindTask_cli.py add "Plan the week" --priority high --due tomorrow
python MindTask_cli.py list --detailed
```

## 4. View History And Undo

```bash
python MindTask_cli.py history
python MindTask_cli.py undo
```

## 5. Optional Interfaces

Interactive shell:

```bash
python MindTask_shell.py
```

MCP JSON-RPC self-test:

```bash
python -m src.mcp.server --test
```
