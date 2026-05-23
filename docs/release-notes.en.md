# Release Notes

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

## 1.2.10 - 2026-05-23

- Summary: Add smoother task creation controls and a dedicated MindTask application icon.
- Changed: Added a create-and-continue action for entering multiple tasks in sequence; allowed the task status to be selected while creating a new task; added the MindTask AI-and-todo app icon as packaged UI assets; set the runtime window/taskbar icon; and configured the Windows packaging script so the generated `MindTask.exe` uses the new icon.
- Verified: Ran Python compile checks, focused icon transparency/loading checks, Qt icon loading smoke checks, and PowerShell syntax checks for the Windows packaging script.

## 1.2.9 - 2026-05-22

- Summary: Fix local timestamp handling and add safer pagination for larger task and history lists.
- Changed: Stored new task, project, and history timestamps in local time instead of UTC; rebuilt timestamp triggers during initialization; avoided refreshing `updated_at` for no-op task/project saves; added task list pagination with 50 tasks per page and history pagination with 100 records per page; added compact shared pagination controls with page jumping, Esc/blur cancellation, and fixed sizing; added configurable `Ctrl+Left` and `Ctrl+Right` page navigation shortcuts; clarified checklist editing hints; shortened the project creation button text; and kept project management unpaged.
- Verified: Ran Python compile checks, CLI version checks, focused timestamp smoke checks, pagination/page-jump/shortcut offscreen UI smoke checks, and PowerShell syntax checks for the Windows packaging script.

## 1.2.8 - 2026-05-21

- Summary: Reorganize UI modules, refresh bilingual documentation, and prepare clearer Windows packages.
- Changed: Grouped UI code by page ownership into task, settings, and shared modules; converted checklist Markdown helpers to the `ChecklistMarkdown` class API; split task and database settings logic into smaller focused modules; refreshed README and user docs with English and Chinese versions; removed obsolete task/search default limit configuration and made CLI list/search/history/export unrestricted unless `--limit` is provided; cleaned stale documentation and empty directories; and updated Windows packaging so `README.md`, `README.zh.md`, and `docs` are included next to `MindTask.exe`.
- Verified: Ran Python compile checks, CLI version and no-limit smoke checks, focused core/database smoke checks, offscreen desktop UI smoke checks for the updated task/settings flows, and PowerShell syntax checks for the Windows packaging script.

## 1.2.7 - 2026-05-21

- Summary: Refine task detail clarity, settings feedback, and database file safety before release.
- Changed: Added a setting to hide completed tasks, unified inline alert messages with severity colors, clarified that checklist items sync from task details, shortened existing task drawer titles to `Task #n`, strengthened database path validation with absolute-path and SQLite suffix requirements, moved database file operations into a dedicated service, supported confirmed overwrite when creating databases, and kept database setting errors as inline danger alerts instead of modal warnings.
- Verified: Ran Python compile checks and offscreen desktop UI smoke checks for hide-completed filtering, alert message timing and sizing, checklist source labeling, task drawer titles, database path validation, existing-database switching, new-database overwrite, and database backup flows.

## 1.2.6 - 2026-05-20

- Summary: Add Markdown-backed checklists to the task detail drawer and tighten task-page drawer behavior.
- Changed: Added checklist parsing from task detail Markdown, rendered editable checklist rows under the details preview, supported draft-only add, edit, toggle, and delete actions that synchronize back to Markdown, added completion-time handling for unfinished checklist items, refined checklist controls and inline editing behavior, disabled accidental mouse-wheel changes on detail combo boxes, closed task-page drawers when leaving the Tasks page, refreshed tasks when returning to the Tasks page, and kept drawer-closing behavior scoped to task-page workflows.
- Verified: Ran Python compile checks, checklist helper assertion checks, PowerShell build-script syntax checks, Windows package build checks, style checks, and offscreen desktop UI smoke checks for checklist add/edit/toggle/delete behavior, completion button state, inline edit focus behavior, no-wheel detail combo boxes, and task-page drawer/page switching.

## 1.2.5 - 2026-05-19

- Summary: Refine task details into a richer drawer workflow with safer editing and history access.
- Changed: Added Markdown-rendered task details with click-to-edit behavior, fixed focus and dirty-field indicators in task detail forms, added due urgency and task metadata to details, moved recent task history into the detail drawer, converted new-task creation and operation history to right-side drawers, required confirmation before discarding edited details or running history undo actions, removed the direct undo shortcut from settings, and refreshed shortcut/config documentation.
- Verified: Ran Python compile checks, whitespace checks, i18n key checks, config cleanup checks for removed shortcut entries, and offscreen desktop UI smoke checks for history drawer shortcut behavior, dirty-detail confirmations, new-task drawer creation, and stale shortcut cleanup.

## 1.2.4 - 2026-05-19

- Summary: Add upcoming due filters and overdue due-date highlighting to the task page.
- Changed: Added an upcoming-due section in the task sidebar with today, tomorrow, 3-day, and 7-day filters that can be combined with project filtering, kept completed tasks out of due-range filters, aligned the project management action with sidebar lists, tightened the upcoming filter layout, and highlighted only the due-date cell for overdue unfinished tasks while keeping all-day tasks unmarked until after their date passes.
- Verified: Ran Python compile checks and offscreen desktop UI checks for upcoming due filter labels, date ranges, project-filter intersection, completed-task exclusion, compact sidebar sizing, project action alignment, and overdue due-cell highlighting.

## 1.2.3 - 2026-05-18

- Summary: Add database backup support and remove unused tag storage.
- Changed: Added a Data settings action to back up the current SQLite database to a timestamped file, documented the backup action, removed unused tag and task-tag tables/views from the schema and core layer, and cleaned obsolete tag structures from existing databases during initialization.
- Verified: Ran Python compile checks, offscreen desktop UI checks for the Data settings backup button, manual backup-file creation smoke checks, new-database schema checks without tag tables, and UI startup checks after cleaning the active database. Full pytest was not run because `pytest` is not installed in the current Python environment.

## 1.2.2 - 2026-05-16

- Summary: Refine the desktop task workspace, settings layout, and all-day due-date model.
- Changed: Moved project management into a right-side task drawer, improved task detail drawer sizing and animation, added an About settings section, reorganized Data settings into clearer database actions, changed all-day due storage to explicit `due_mode = all_day` with `00:00:00`, removed the obsolete latest-work-time setting from UI and config, and updated Chinese all-day wording.
- Verified: Ran Python compile checks, offscreen desktop UI checks for settings sections, project and task drawers, all-day due editing and display, and manual core database checks for `due_mode` storage. Full pytest was not run because `pytest` is not installed in the current Python environment.

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
