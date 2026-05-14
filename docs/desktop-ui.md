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

The current visual style is a restrained desktop tool layout with light panels, visible section boundaries, colored status and priority cells, and an empty-state message for task lists.

The Settings page includes:

- Theme selection: `system`, `light`, and `dark`
- Active config file path
- Database path
- Database creation with sample projects and tasks

The default theme is `system`, which follows the operating system color scheme when Qt can detect it.
Theme selection is saved to the active config file under `ui.theme`.

Changing the database path requires clicking `Apply Database`. MindTask first attempts to open and read the database at the new path. The active config and UI data source are updated only after that check succeeds.

Creating a database requires entering a path that does not already exist and clicking `Create Database`. MindTask initializes that database, adds explicit sample data, saves the new path to the active config, and switches the UI to the new database.

## Current Actions

- List tasks
- Search tasks
- Filter by project
- Manage projects
- Create a task
- Edit title, description, status, priority, project, and due date
- Complete a task
- Delete a task
- Open operation history
- Undo the latest operation from the history window
- Undo operations from the latest down to a selected history record

Due dates use the same core format as the other software interfaces:

```text
YYYY-MM-DD HH:MM:SS
```

## Next UI Work

- Add tag management screens
- Add a board view grouped by task status
- Add richer history inspection
- Add packaging scripts for Windows desktop distribution
