# Desktop UI

MindTask includes a PySide6 desktop UI entry point for daily task work.

## Run

Install the UI dependency:

```bash
pip install -e .[ui]
```

Start the desktop app:

```bash
python MindTask_ui.py
```

On first launch, if the active config file does not exist, MindTask copies `config/mindtask.ini.template` to that location and opens a welcome setup window. The setup flow asks the user to choose a language, then choose either an existing database or a new database. The main window opens only after setup is complete. If the template is missing, startup fails with an error.

Use a custom config file:

```bash
python MindTask_ui.py --config path/to/mindtask.ini
```

## Current Layout

The UI uses a page-based desktop layout with bottom navigation so new features can be added without crowding the task workspace.

Current pages:

- Tasks
- Projects
- Settings

The Tasks page uses a three-panel layout:

- Left: project navigation
- Center: task table with search
- Right: selected task detail editor

The Projects page lists project task counts and supports:

- Creating projects
- Renaming projects
- Deleting projects

Projects that still contain tasks cannot be deleted from the UI.

Tasks are ordered by `id` ascending by default.

The UI calls the existing `MindTaskDB` core directly. It does not shell out to the CLI.

The current visual style is a restrained desktop tool layout with compact panels, clear page structure, colored status and priority cells, and an empty-state message for task lists.

The Settings page includes:

- General settings: theme selection, language selection, and latest work time for all-day due dates
- Data settings: active config file path, database path, and database creation with sample projects and tasks
- Keyboard shortcut settings

The default theme is `system`, which follows the operating system color scheme when Qt can detect it.
Theme selection is saved to the active config file under `ui.theme`.
The default language is `en`. Language selection is saved to the active config file under `ui.language`.
The default latest work time for all-day due dates is `same_day`, which stores all-day task due dates as `23:59:59` on the selected date. Users who treat late-night work as part of the previous day can choose `next_day_early_morning`, which stores all-day due dates as `04:59:59` on the next day.

Changing the database path requires clicking `Apply Database`. MindTask first attempts to open and read the database at the new path. The active config and UI data source are updated only after that check succeeds.

Creating a database requires entering a path that does not already exist and clicking `Create Database`. MindTask initializes that database, adds explicit sample data, saves the new path to the active config, and switches the UI to the new database.

## Current Actions

- List tasks
- Search tasks
- Filter by project
- Manage projects
- Create a task
- Edit title, description, status, priority, project, and due date with date/time pickers
- Complete a task
- Delete a task
- Open operation history
- Undo the latest operation from the history window
- Undo operations from the latest down to a selected history record

## Keyboard Shortcuts

Shortcuts are active while the MindTask window has focus.
They can be changed from Settings. The saved values are stored in the config file under `[shortcuts]`.
Shortcut rows show a focused state while editing and a separate modified state before changes are saved. Each row can be restored to its saved value or reset to the default value, and the Settings page also includes a reset-all-defaults action. Mouse clicks only focus a shortcut field; shortcut recording uses keyboard input.
Shortcut rows turn red when a shortcut is duplicated or may conflict with normal text input. Single-key shortcuts are limited to `Esc` and `F1` through `F12`; other keys require `Ctrl`, `Alt`, or `Meta`.

- `Ctrl+1`: Open Tasks
- `Ctrl+2`: Open Projects
- `Ctrl+3`: Open Settings
- `Ctrl+N`: Create a task from the Tasks page
- `Ctrl+F`: Focus task search from the Tasks page
- `Esc`: Close task details first; if details are closed, clear active search
- `F5`: Refresh data
- `Ctrl+U`: Undo the latest operation
- `Ctrl+H`: Open operation history
- `Ctrl+S`: Save the open task details
- `Ctrl+Enter`: Complete the open task
- `Ctrl+R`: Delete the open task, with confirmation

Due dates use the same core format as the other software interfaces:

```text
YYYY-MM-DD HH:MM:SS
```

## Windows Packaging

The Windows build script creates a portable desktop package:

```powershell
.\scripts\build_windows.ps1
```

It installs UI packaging dependencies with the Tsinghua PyPI mirror by default, builds `dist\MindTask\MindTask.exe`, and creates a versioned zip file under `dist\`.

## Next UI Work

- Add tag management screens
- Add a board view grouped by task status
- Add richer history inspection
