# MindTask

[中文](README.zh.md) | English

MindTask is a desktop-first task manager built around a local SQLite database. It focuses on compact daily task work: fast task capture, clear tables, practical drawers, Markdown details, checklist drafting, project filtering, history rollback, and predictable settings.

The desktop UI is the primary experience. CLI commands exist for scripts and debugging.

MindTask is developed with assistance from Codex.

## Highlights

- **Markdown-backed checklist editing**: checklist rows are parsed from task details, edited in a dedicated checklist area, and synchronized back to the Markdown draft.
- **Draft-first task drawer**: task edits, checklist changes, and completion checks happen against the current draft before anything is written to the database.
- **Scoped history rollback**: write operations are recorded and can be undone from the history drawer, including rolling back from the latest operation down to a selected history record.
- **Config-driven local database switching**: the app can switch, create, overwrite, reload, and back up SQLite databases from the desktop Data settings page with path and schema validation.
- **Desktop workflow over dialogs**: task creation, task editing, project management, recent task history, and global history use right-side drawers instead of a chain of modal windows.

## Main Features

MindTask currently includes:

- Task creation, editing, completion, deletion, and search
- Markdown-rendered task details
- Interactive checklists synchronized from Markdown
- Due date modes: no due date, all day, and exact time
- Project management and project filtering
- Upcoming-due filters with overdue unfinished tasks included
- Status and priority presentation in compact tables
- Recent task history in the task detail drawer
- Global operation history with undo
- Runtime English and Chinese UI localization
- Light, dark, and system theme modes
- Configurable keyboard shortcuts
- Database switching, creation, overwrite confirmation, reload, and backup
- CLI commands for automation and debugging

## Quick Start

Install UI dependencies and open the desktop app:

```bash
pip install -e .[ui]
python MindTask_ui.py
```

On first launch, MindTask creates the active config from `config/mindtask.ini.template` and opens the welcome setup flow. Choose a language, then open an existing database or create a new one.

The default local database is `data/mindtask.db`.

## Documentation

- [Docs Index](docs/index.md)
- [Getting Started](docs/getting-started.en.md) / [新手入门](docs/getting-started.zh.md)
- [Desktop Guide](docs/desktop-guide.en.md) / [桌面端指南](docs/desktop-guide.zh.md)
- [CLI Reference](docs/cli-reference.en.md) / [CLI 参考](docs/cli-reference.zh.md)
- [Release Notes](docs/release-notes.en.md) / [发布记录](docs/release-notes.zh.md)

## Project Structure

```text
MindTask/
  src/
    core/      SQLite access and business logic
    cli/       Script/debug command interface
    ui/        PySide6 desktop UI
  sql/         SQLite schema
  config/      Config template
  docs/        User and maintenance documentation
```

## Configuration

Default settings live in `config/mindtask.ini.template`. MindTask creates the active config from that template when the config file is missing. The database path comes from config and can be changed through the desktop Data settings page.

Local database files and generated config files are not meant to be committed.

## Development

Install development dependencies:

```bash
pip install -e .[dev]
```

Useful checks:

```bash
python -m compileall src tests
pytest
```

Build a Windows portable package:

```powershell
.\scripts\build_windows.ps1
```

The build output is written under `dist\`.
The portable app directory and zip include `README.md`, `README.zh.md`, and `docs` next to `MindTask.exe`.
