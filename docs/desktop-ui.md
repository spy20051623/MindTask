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

The current visual style is a restrained desktop tool layout with light panels, visible section boundaries, colored status and priority cells, and an empty-state message for task lists.

The Settings page includes:

- Theme selection: `system`, `light`, and `dark`
- Language selection: `en` and `zh`
- Date-only due time: selected day `23:59:59` or next day `04:59:59`
- Active config file path
- Database path
- Database creation with sample projects and tasks

The default theme is `system`, which follows the operating system color scheme when Qt can detect it.
Theme selection is saved to the active config file under `ui.theme`.
The default language is `en`. Language selection is saved to the active config file under `ui.language`.
The default date-only due time is `same_day`, which stores selected-date-only due dates as `23:59:59` on that date. Users who treat late-night work as part of the previous day can choose `next_day_early_morning`, which stores them as `04:59:59` on the next day.

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

Due dates use the same core format as the other software interfaces:

```text
YYYY-MM-DD HH:MM:SS
```

## Next UI Work

- Add tag management screens
- Add a board view grouped by task status
- Add richer history inspection
- Add packaging scripts for Windows desktop distribution
