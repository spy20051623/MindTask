# Getting Started

This guide is for first-time desktop UI users. It walks through opening MindTask, completing first-run setup, creating a first task, using Markdown details and checklists, and finding the most important settings.

## 1. Install And Open MindTask

Install the desktop UI dependencies:

```bash
pip install -e .[ui]
```

Open the app:

```bash
python MindTask_ui.py
```

MindTask stores its active configuration in `config/mindtask.ini`. If that file does not exist, MindTask creates it from `config/mindtask.ini.template` and opens the welcome setup window.

## 2. Complete First-Run Setup

The welcome setup has two decisions:

1. Choose a language.
2. Choose a database.

For a new user, choose **Create new database**. Pick an absolute file path ending in `.db`, `.sqlite`, or `.sqlite3`.

Example paths:

```text
C:\Users\you\Documents\MindTask\mindtask.db
C:\Users\you\Documents\MindTask\personal-tasks.sqlite3
```

If you already have a MindTask database, choose **Use existing database** and select that file instead.

The main window opens after setup succeeds.

## 3. Understand The Main Window

MindTask starts on the Tasks page.

The page has three main areas:

- **Left side**: upcoming-due filters and project filters
- **Center**: task table
- **Right side**: task detail drawer, shown when creating or selecting a task

The bottom navigation switches between **Tasks** and **Settings**.

The status bar at the bottom shows persistent page counts, such as how many tasks are currently shown. It also reports operations like saving, creating, deleting, backing up a database, or undoing history.

## 4. Create Your First Task

On the Tasks page, press `Ctrl+N` or click the new-task action.

In the task detail drawer:

1. Enter a title, such as `Plan the week`.
2. Add details, such as notes or a short plan.
3. Choose a priority if needed.
4. Choose a project if you have one.
5. Set a due date if the task has a deadline.
6. Click **Create**.

The task appears in the task table after it is created.

## 5. Add Markdown Details

Task details support Markdown. You can write plain text, or use simple Markdown formatting:

```markdown
Prepare the weekly plan.

## Focus

- Review unfinished tasks
- Pick the top priorities
- Check calendar conflicts
```

MindTask shows rendered Markdown by default. Enter edit mode only when you want to change the details.

Press `Esc` to leave Markdown editing before closing the task drawer.

## 6. Use A Checklist

Checklist items are written in the task details as Markdown:

```markdown
- [ ] Review unfinished tasks
- [ ] Pick top priorities
- [x] Clean up old notes
```

MindTask reads those lines and shows them in a checklist area below the rendered details.

From the checklist area you can:

- Mark an item complete
- Add a new item
- Delete an item after confirmation
- Double-click an item name to edit it

Checklist edits update the task detail draft. They are saved to the database only after you click **Save**.

If you complete a task while checklist items are still unfinished, MindTask asks what to do. You can complete the task anyway, mark all checklist items complete and save, or cancel.

## 7. Set A Due Date

The task drawer has three due-date modes:

- **No due date**: the task has no deadline.
- **All day**: the task is due on a date, without a specific time.
- **Exact time**: the task is due at a specific date and time.

Focusing or editing the date switches to all-day mode. Focusing or editing the time switches to exact-time mode.

Use the left-side upcoming filters to quickly see tasks due today, tomorrow, within 3 days, or within 7 days. Overdue unfinished tasks are included in those due filters.

## 8. Organize With Projects

Projects are managed from the Tasks page.

Open project management with `Ctrl+P` or the project action in the task sidebar.

You can:

- Create a project, such as `Work`, `Personal`, or `Reading`
- Rename a project
- Delete an empty project

Projects that still contain tasks cannot be deleted from the UI. Move or delete those tasks first.

## 9. Search, Sort, And Filter

Use the search box on the Tasks page to find tasks by text.

Use project filters to show tasks for a specific project.

Use the due filters to focus on upcoming work.

By default, smart sorting keeps unfinished tasks above completed tasks and orders unfinished tasks by due date and priority. You can still click table headers to sort; the active header sort is used when smart sorting cannot otherwise distinguish two tasks.

## 10. Save, Complete, Or Delete A Task

When editing a task:

- Click **Save** to save draft changes.
- Click the complete action or press `Ctrl+Enter` to complete it.
- Click delete or press `Ctrl+R` to delete it after confirmation.

If you edit a task and then try to switch away, MindTask asks before discarding unsaved changes.

## 11. Undo From History

MindTask records write operations in history.

Open global history from the Tasks page with `Ctrl+H`.

You can undo the latest operation, or undo from the latest operation down to a selected history record. Undo actions ask for confirmation before changing data.

Recent history for the selected task is also shown inside the task detail drawer.

## 12. Adjust Settings

Open the Settings page from the bottom navigation.

General settings:

- Theme
- Language
- Smart task sorting
- Hide completed tasks

Data settings:

- Reload the current database
- Back up the current database
- Switch to another existing MindTask database
- Create a new database

Keyboard shortcut settings:

- Edit shortcuts
- Restore a saved shortcut
- Reset shortcuts to defaults

Database paths must be absolute and must end in `.db`, `.sqlite`, or `.sqlite3`. Existing databases must be valid MindTask SQLite databases. If you create a new database at an existing path, MindTask asks before overwriting it.

## 13. A Good First Workflow

Try this small workflow to get comfortable:

1. Create a project named `Personal`.
2. Create a task named `Plan the week`.
3. Add these details:

   ```markdown
   Prepare a simple weekly plan.

   - [ ] Review unfinished tasks
   - [ ] Choose three priorities
   - [ ] Check the calendar
   ```

4. Set the task to due tomorrow.
5. Save the task.
6. Use the checklist area to complete one item.
7. Save again.
8. Open history and confirm that the save was recorded.

After that, the main pieces of the desktop UI should feel familiar.
