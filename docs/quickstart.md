# Quickstart

## 1. Check Configuration

MindTask reads fixed settings from `config/mindtask.ini`.

```ini
[database]
path = data/mindtask.db
```

## 2. Initialize The Database

```bash
python scripts/setup_MindTask_db.py
```

## 3. Create And List Tasks

```bash
python MindTask_cli.py add "Plan the week" --priority high --due "2026-05-15 18:00:00"
python MindTask_cli.py list --detailed
```

## 4. View History And Undo

```bash
python MindTask_cli.py history
python MindTask_cli.py undo
```

## 5. Optional Interfaces

MCP JSON-RPC self-test:

```bash
python -m src.mcp.server --test
```
