# CLI Reference

The CLI is a script and debugging interface for MindTask. The desktop UI is the primary user experience; use the CLI when you need quick checks, automation, exports, or troubleshooting.

Main entry point:

```bash
python MindTask_cli.py <command> [options]
```

You can also use the installed console command:

```bash
mindtask <command> [options]
```

## Global Option

Use a custom config file:

```bash
python MindTask_cli.py --config PATH <command> [options]
```

Example:

```bash
python MindTask_cli.py --config config/dev.ini list
```

The database path is read from the active config file. The CLI does not accept a direct database path option.

Without `--config`, the CLI looks for local `config/mindtask.ini` first, then `%APPDATA%\MindTask\mindtask.ini`. If no config file exists, the CLI reports an error instead of creating one. Start the desktop UI to complete first-run setup.

If the active config points to a missing or unusable database file, the CLI reports an error and does not create a database.

## Common Values

Priority values:

```text
none | low | medium | high
0    | 1   | 2      | 3
```

Status values:

```text
not_started | in_progress | suspended | completed
0           | 1           | 2         | 3
```

Due dates use this format:

```text
YYYY-MM-DD HH:MM:SS
```

Example:

```text
2026-05-15 18:00:00
```

When updating a task, use `--due none` to clear the due date.

## Projects

### List Projects

Format:

```bash
python MindTask_cli.py projects
```

Use this to find project IDs before creating or updating tasks.

Example:

```bash
python MindTask_cli.py projects
```

Output format:

```text
[1] Work  Work tasks
[2] Personal
```

### Create Project

Format:

```bash
python MindTask_cli.py project-add NAME [--description TEXT] [--color HEX]
```

Examples:

```bash
python MindTask_cli.py project-add Work
python MindTask_cli.py project-add Personal --description "Personal tasks"
python MindTask_cli.py project-add Reading --color "#7C3AED"
```

Notes:

- `NAME` is required.
- `--description` is optional.
- `--color` defaults to `#007BFF`.

## Tasks

### List Tasks

Format:

```bash
python MindTask_cli.py list [--project ID] [--status STATUS] [--priority 0|1|2|3] [--limit N] [--detailed] [--json]
```

Examples:

```bash
python MindTask_cli.py list
python MindTask_cli.py list --detailed
python MindTask_cli.py list --project 1
python MindTask_cli.py list --status in_progress
python MindTask_cli.py list --priority 3
python MindTask_cli.py list --limit 10
python MindTask_cli.py list --json
```

Notes:

- Tasks are ordered by ID ascending by default.
- `--project` filters by project ID.
- `--status` accepts names or numbers.
- `--priority` accepts numbers only for list filtering.
- `--detailed` includes project, due date, and description.
- `--json` prints the raw task rows as JSON.

### Create Task

Format:

```bash
python MindTask_cli.py add TITLE [-d TEXT|--description TEXT] [-p ID|--project ID] [--priority PRIORITY] [--due "YYYY-MM-DD HH:MM:SS"]
```

Examples:

```bash
python MindTask_cli.py add "Plan the week"
python MindTask_cli.py add "Write report" --priority high
python MindTask_cli.py add "Write report" --description "Draft the quarterly summary"
python MindTask_cli.py add "Prepare meeting" --project 1 --priority 2 --due "2026-05-15 18:00:00"
```

Notes:

- `TITLE` is required.
- Default priority is `medium`.
- Use `projects` first if you need to find a project ID.
- Due dates must use the standard timestamp format.

### Show Task

Format:

```bash
python MindTask_cli.py show TASK_ID
```

Example:

```bash
python MindTask_cli.py show 12
```

This prints the full task row as JSON, including fields that the compact list view does not show.

### Update Task

Format:

```bash
python MindTask_cli.py update TASK_ID [--title TEXT] [--description TEXT] [--project ID] [--priority PRIORITY] [--status STATUS] [--due VALUE]
```

Examples:

```bash
python MindTask_cli.py update 12 --title "Plan next week"
python MindTask_cli.py update 12 --description "Update the draft plan"
python MindTask_cli.py update 12 --project 2
python MindTask_cli.py update 12 --priority high
python MindTask_cli.py update 12 --status in_progress
python MindTask_cli.py update 12 --due "2026-05-16 09:30:00"
python MindTask_cli.py update 12 --due none
python MindTask_cli.py update 12 --status suspended --priority low
```

Notes:

- At least one field option is required.
- `--priority` accepts names or numbers.
- `--status` accepts names or numbers.
- `--due none` clears the due date.
- Updating a missing task returns a non-zero exit code.

### Complete Task

Format:

```bash
python MindTask_cli.py complete TASK_ID
```

Example:

```bash
python MindTask_cli.py complete 12
```

This marks the task as completed and records the completion time.

### Delete Task

Format:

```bash
python MindTask_cli.py delete TASK_ID [-y|--yes]
```

Examples:

```bash
python MindTask_cli.py delete 12
python MindTask_cli.py delete 12 --yes
```

Notes:

- Without `--yes`, the CLI asks for confirmation.
- Type `yes` to confirm.
- Use `--yes` for scripts where interactive confirmation is not possible.

## Search

### Search Tasks

Format:

```bash
python MindTask_cli.py search KEYWORD [--limit N] [--detailed] [--json]
```

Examples:

```bash
python MindTask_cli.py search report
python MindTask_cli.py search "weekly plan" --detailed
python MindTask_cli.py search report --limit 5
python MindTask_cli.py search report --json
```

Notes:

- Search uses the core task search behavior.
- Without `--limit`, all matching tasks are returned.
- `--detailed` includes project, due date, and description.

## Stats

### Show Stats

Format:

```bash
python MindTask_cli.py stats [--json]
```

Examples:

```bash
python MindTask_cli.py stats
python MindTask_cli.py stats --json
```

The text output includes total tasks, status counts, completion rate, and upcoming tasks in 3 days.

Use `--json` when another script needs to parse the result.

## Export

### Export Tasks

Format:

```bash
python MindTask_cli.py export [--format json|csv] [--output PATH] [--limit N]
```

Examples:

```bash
python MindTask_cli.py export
python MindTask_cli.py export --format json --output tasks.json
python MindTask_cli.py export --format csv --output tasks.csv
python MindTask_cli.py export --limit 100
```

Notes:

- Default format is `json`.
- Without `--limit`, all tasks are exported.
- Without `--output`, the export is printed to standard output.
- CSV output includes common task fields such as ID, title, description, project name, priority, status, due date, and creation time.

## History And Undo

MindTask records write operations in `operation_history`.

### Show History

Format:

```bash
python MindTask_cli.py history [--limit N] [--all] [--json]
```

Examples:

```bash
python MindTask_cli.py history
python MindTask_cli.py history --limit 20
python MindTask_cli.py history --all
python MindTask_cli.py history --json
```

Notes:

- Without `--limit`, all matching history records are returned.
- By default, already undone operations are hidden.
- Use `--all` to include already undone operations.
- Use `--json` for full row data.

### Undo Latest Operation

Format:

```bash
python MindTask_cli.py undo
```

Example:

```bash
python MindTask_cli.py undo
```

`undo` rolls back the latest operation that has not already been undone.

Notes:

- Undo changes data.
- The CLI undo command only targets the latest undoable operation.
- For visual history browsing and selected-record rollback, use the desktop UI history drawer.

## Version

### Show Version

Format:

```bash
python MindTask_cli.py version
```

Example:

```bash
python MindTask_cli.py version
```

This prints the package version.

## Common Workflows

### Create A Project And Task

```bash
python MindTask_cli.py project-add Work --description "Work tasks"
python MindTask_cli.py projects
python MindTask_cli.py add "Write weekly report" --project 1 --priority high --due "2026-05-15 18:00:00"
python MindTask_cli.py list --project 1 --detailed
```

### Update And Complete A Task

```bash
python MindTask_cli.py update 1 --status in_progress
python MindTask_cli.py update 1 --description "Draft is ready for review"
python MindTask_cli.py complete 1
python MindTask_cli.py show 1
```

### Export A Small CSV

```bash
python MindTask_cli.py export --format csv --limit 50 --output tasks.csv
```

### Check And Undo The Latest Change

```bash
python MindTask_cli.py history --limit 5
python MindTask_cli.py undo
python MindTask_cli.py history --all --limit 5
```
