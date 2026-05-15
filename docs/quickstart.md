# Quickstart

## 1. Check Configuration

MindTask creates `config/mindtask.ini` from `config/mindtask.ini.template` when the config file is missing.

```ini
[database]
path = data/mindtask.db
```

The database is created automatically the first time MindTask runs.

## 2. Open The Desktop UI

```bash
pip install -e .[ui]
python MindTask_ui.py
```

## 3. Optional CLI Smoke Check

```bash
python MindTask_cli.py add "Plan the week" --priority high --due "2026-05-15 18:00:00"
python MindTask_cli.py list --detailed
```

## 4. View History And Undo From The CLI

```bash
python MindTask_cli.py history
python MindTask_cli.py undo
```
