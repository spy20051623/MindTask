# Desktop Guide

MindTask is designed as a desktop-first task manager. The PySide6 UI is the primary daily workflow; CLI commands are software interfaces for scripts and debugging.

The desktop UI calls the `MindTaskDB` core directly. It does not shell out to the CLI.

## Run

Install the UI dependency:

```bash
pip install -e .[ui]
```

Start the desktop app:

```bash
python MindTask_ui.py
```

Use a custom config file:

```bash
python MindTask_ui.py --config path/to/mindtask.ini
```

On first launch, if the active config file does not exist, MindTask copies `config/mindtask.ini.template` to that location and opens a welcome setup window. The setup flow asks for a language and then asks the user to open an existing database or create a new one. The main window opens only after setup is complete. If the template is missing, startup fails with a clear error.

## Layout

The UI uses compact desktop pages with bottom navigation and right-side drawers for supporting workflows.

Primary pages:

- Tasks
- Settings

The Tasks page is the main workspace:

- Left: upcoming-due filters and project navigation
- Center: searchable task table
- Right: task detail drawer when a task is selected or a new task is being created

Upcoming-due filters include today, tomorrow, 3 days, and 7 days. Each due filter also includes overdue unfinished tasks.

When leaving the Tasks page, open task-page drawers are closed. If the task detail drawer contains unsaved changes, MindTask asks before discarding them. Returning to the Tasks page refreshes the task list.

The status bar keeps persistent counts for the active page, such as the number of tasks, projects, or history records. It also reports operations whose result is not obvious from the immediate UI change, such as saving, creating, deleting, switching databases, backing up databases, and undoing history.

## Tasks

The task table supports search, project filtering, due filtering, and header sorting. Search belongs to the Tasks page; if a search result is active, the clear action remains available even after the search box is manually emptied.

Smart sorting is enabled by default. Unfinished tasks appear before completed tasks. Unfinished tasks sort by due date, then priority; completed tasks sort by completion time. The active table sort is used when the smart rules cannot distinguish two tasks, with ID as the stable fallback.

The Settings page includes an option to hide completed tasks from the task list.

## Task Details

Task creation and editing both use the task detail drawer.

Editable fields:

- Title
- Details
- Status
- Priority
- Project
- Due date

The Details field uses Markdown. MindTask shows rendered Markdown by default; entering Markdown edit mode is intentional. `Esc` leaves Markdown editing before it closes the drawer.

Task detail changes remain a draft until the user saves. If the user tries to close, reload, switch tasks, switch filters, or open another task-page drawer while the draft is dirty, MindTask asks for confirmation unless the action is an explicit cancel or discard.

## Checklist

Checklist items are parsed from the task detail Markdown and shown below the rendered details with the label `Synced from task details`.

Supported Markdown checklist lines:

```text
- [ ] Unfinished item
- [x] Finished item
```

Checklist actions update the Markdown draft:

- Toggle completion from the checklist row
- Add an item from the checklist toolbar
- Delete an item after confirmation
- Edit an item name directly in the checklist area

Checklist changes are not written to the database until the task is saved. If the user completes a task while the current draft still has unfinished checklist items, MindTask asks whether to complete anyway, mark all checklist items complete and save, or cancel.

## Due Dates

Due dates use the same core storage format as other interfaces:

```text
YYYY-MM-DD HH:MM:SS
```

The UI presents three modes:

- No due date
- All day
- Exact time

Focusing or editing the date switches to all-day mode. Focusing or editing the time switches to exact-time mode. Time suggestions use half-hour increments, while precise manual input remains possible.

All-day tasks are stored with `due_mode = all_day` and `due_date` at `00:00:00` on the selected date.

## Projects And History

Project management opens as a right-side drawer inside the Tasks page. It supports creating, renaming, and deleting projects. Projects that still contain tasks cannot be deleted from the UI.

Recent task history is shown inside the task detail drawer. Global operation history opens as a right-side drawer from the Tasks page. Undo actions require confirmation. Undoing a selected history record rolls back operations from the latest record down to that selected point.

## Settings

The Settings page includes:

- General settings: theme, language, smart task sorting, and hiding completed tasks
- Data settings: current database, reload, backup, switch existing database, and create new database
- Keyboard shortcuts
- About: app version, config file path, and active database path

Theme selection is saved under `ui.theme`. Language selection is saved under `ui.language`.

Database settings validate file paths before switching or creating databases:

- Paths must be absolute.
- File suffix must be `.db`, `.sqlite`, or `.sqlite3`.
- Existing databases must be valid SQLite files.
- Existing databases must contain the MindTask schema.
- Creating a database over an existing valid-suffix file asks for confirmation before overwriting.

Database setting errors are shown as inline danger alerts in the settings page instead of modal warning dialogs.

## Keyboard Shortcuts

Shortcuts are active while the MindTask window has focus. They can be changed from Settings and are stored in the config file under `[shortcuts]`.

Shortcut rows show focused, modified, duplicate, and invalid states. Each row can be restored to its saved value or reset to the default value. Mouse clicks only focus a shortcut field; shortcut recording uses keyboard input.

Single-key shortcuts are limited to `Esc` and `F1` through `F12`; other keys require `Ctrl`, `Alt`, or `Meta`.

Default shortcuts:

- `Ctrl+1`: Open Tasks
- `Ctrl+2`: Open Settings
- `Ctrl+P`: Open or close project management
- `Ctrl+N`: Create a task from the Tasks page
- `Ctrl+F`: Focus task search from the Tasks page
- `Esc`: Leave local editing first, then close task details; if details are closed, clear active search
- `F5`: Refresh data
- `Ctrl+H`: Open operation history, or close it when it is already open on the Tasks page
- `Ctrl+S`: Save the open task details
- `Ctrl+Enter`: Complete the open task
- `Ctrl+R`: Delete the open task, with confirmation
- `Ctrl+Left`: Previous page in paged task/history lists
- `Ctrl+Right`: Next page in paged task/history lists

## Maintenance Notes

UI code is grouped by ownership:

- `src/ui/tasks`: task page, task drawers, task detail helpers, checklist, due-date editor, projects
- `src/ui/settings`: settings page, database settings, shortcut settings, toggle controls
- `src/ui/shared`: shared styles, icons, i18n, alerts, status bar, constants, and dialog helpers

User-facing fixed text should be localizable through `src/ui/shared/i18n.py`.

After UI changes, run Python compile checks and focused offscreen Qt smoke checks when a full interactive run is unnecessary.

## Windows Packaging

The Windows build script creates a portable desktop package:

```powershell
.\scripts\build_windows.ps1
```

It builds `dist\MindTask\MindTask.exe` and creates a versioned zip file under `dist\`. The portable app directory and zip include `README.md`, `README.zh.md`, and `docs` next to `MindTask.exe`.
