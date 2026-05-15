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

## 1.2.1 - 2026-05-15

- Summary: Fix shortcut editing and validation edge cases after the 1.2.0 release.
- Changed: Disabled window shortcuts while editing shortcut fields so saved shortcuts can be re-entered, normalized Enter handling so both keyboard Enter keys are treated as `Enter`, added real-time red warnings and save blocking for duplicate or input-conflicting shortcuts, changed the default undo shortcut from `Ctrl+Z` to `Ctrl+U`, and normalized shifted key shortcuts such as `Ctrl+Shift+1` so they do not save or trigger as `Ctrl+Shift+!`.
- Verified: Ran Python compile checks and offscreen desktop UI checks for shortcut focus handling, Enter normalization, duplicate and invalid shortcut warnings, save rejection, and shifted-key shortcut registration.

## 1.2.0 - 2026-05-15

- Summary: Prepare a leaner desktop-focused release with modular UI code, Windows packaging, and obsolete interface cleanup.
- Changed: Split the large desktop main window into task, project, settings, shortcut settings, and shortcut editor modules; added a Windows portable packaging script that bundles the desktop app and uses the Tsinghua PyPI mirror for dependency installation; removed the old MCP-style JSON-RPC server, unused initialization scripts, and related documentation/tests; refreshed README and docs to reflect the desktop-first workflow, automatic database initialization, configurable shortcuts, and current packaging flow.
- Verified: Ran Python compile checks, offscreen desktop UI smoke checks for the modularized settings and shortcut behavior, PowerShell syntax checks for the packaging script, and documentation searches for obsolete MCP and initialization-script references. Full pytest was not run because `pytest` is not installed in the current Python environment.

## 1.1.4 - 2026-05-15

- Summary: Add configurable desktop shortcuts and reorganize settings for clearer daily use.
- Changed: Added configurable window-scoped keyboard shortcuts with per-action reset/cancel controls, duplicate shortcut validation, shortcut settings persisted in config, a custom keyboard-only shortcut editor, reorganized settings into General, Data, and Keyboard Shortcuts sections with a task-page-style sidebar, refined settings feedback messages, and updated all-day due settings wording to latest work time.
- Verified: Ran Python compile checks, config shortcut smoke checks, and offscreen desktop UI smoke checks for shortcut editing, settings section navigation, full-height settings layout, inline settings messages, and latest work time text.

## 1.1.3 - 2026-05-15

- Summary: Improve desktop task editing ergonomics and table navigation.
- Changed: Added reusable date/time picker controls for task due dates, configurable all-day due boundaries, half-hour time suggestions with editable precise times, automatic due mode switching from date/time focus, wider task detail drawer defaults, sortable task and project tables, and clearer search reset behavior.
- Verified: Ran Python compile checks, whitespace checks, CLI version check, config due-time checks, and offscreen desktop UI smoke checks for due-date editing, task dialogs, search reset, and task/project table sorting.

## 1.1.2 - 2026-05-14

- Summary: Prepare first-run configuration and clean up desktop UI module structure.
- Changed: Removed the generated `config/mindtask.ini` from the repository, added `config/mindtask.ini.template` as the default configuration source, added the first-run welcome setup flow for language and database selection, added database path browsing in settings, and split desktop UI dialogs, constants, helpers, and icon handling into focused modules.
- Verified: Ran Python compile checks, whitespace checks, and offscreen desktop UI smoke checks for main pages and dialogs.

## 1.1.1 - 2026-05-14

- Summary: Add desktop UI localization and simplify user-facing configuration.
- Changed: Added English and Chinese runtime translations for desktop UI text, buttons, dialogs, status and priority labels, history labels, and settings options; removed the language `system` option; localized theme choices; removed schema path from user config while keeping the schema file path internal.
- Verified: Ran Python compile checks, CLI version check, UI localization smoke checks, dialog button localization checks, theme option localization checks, and config compatibility checks for language and schema cleanup.

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
