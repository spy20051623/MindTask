# Iteration Log

This file is maintained by version.

Update it immediately before creating a release commit, not after every local change. Each entry should describe the user-visible or project-level outcome of that version.

## Format

```text
## <version> - <YYYY-MM-DD>

- Summary: <one sentence>
- Changed: <notable implementation or documentation changes>
- Verified: <checks run before release commit>
```

## Entries

## 1.1.0 - 2026-05-14

- Summary: Add the first desktop UI iteration and project/database management workflows.
- Changed: Added the PySide6 desktop UI, theme settings, task search and editing screens, operation history viewing and scoped undo from the UI, project management, QtAwesome action icons with fallback labels, configurable database switching, explicit sample-data database creation, and removed automatic default project seeding.
- Verified: Ran Python compile checks, UI smoke checks for task/project/settings pages, and manual core validation scripts for project management, database creation, sample data, and default project initialization.

## 1.0.1 - 2026-05-14

- Summary: Simplify MindTask's software-facing interfaces before the desktop UI iteration.
- Changed: Removed the interactive shell, standardized task status values for CLI/MCP use, required fixed due-date strings, moved due-date validation into the core layer, and documented Codex-assisted development.
- Verified: Ran Python compile checks, CLI help and smoke checks, MCP self-test, and manual due-date validation with Python 3.10.11.

## 1.0.0 - 2026-05-14

- Summary: Prepare MindTask 1.0.0 with cleaned project structure, configuration-driven database access, operation history, undo support, and documented CLI/MCP workflows.
- Changed: Rebuilt the core SQLite layer, CLI, MCP JSON-RPC server, schema, docs, tests, configuration, history tracking, and version command.
- Verified: Ran Python compile checks, CLI smoke checks, MCP self-test, and manual history/undo validation with Python 3.10.11.
