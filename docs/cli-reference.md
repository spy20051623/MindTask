# CLI Reference

Main entry point:

```bash
python MindTask_cli.py <command> [options]
```

Global option:

- `--config PATH`: use a custom MindTask config file

## Task Commands

```bash
python MindTask_cli.py add "Write report" --description "Quarterly summary" --priority high --due "2026-05-15 18:00:00"
python MindTask_cli.py list --status in_progress --priority 3 --detailed
python MindTask_cli.py show 1
python MindTask_cli.py update 1 --status suspended
python MindTask_cli.py complete 1
python MindTask_cli.py delete 1
```

Task options:

- `--priority none|low|medium|high` or `0|1|2|3`
- `--status not_started|in_progress|suspended|completed` or `0|1|2|3`
- `--due "YYYY-MM-DD HH:MM:SS"` or `none` when updating
- `--limit N`
- `--json`

Task lists are ordered by `id` ascending by default.

## Project Commands

```bash
python MindTask_cli.py projects
python MindTask_cli.py project-add Work --description "Work tasks"
```

## Search, Stats, Export

```bash
python MindTask_cli.py search report
python MindTask_cli.py stats
python MindTask_cli.py stats --json
python MindTask_cli.py export --format csv --output tasks.csv
```

## History And Undo

Every write operation is recorded in `operation_history`.

```bash
python MindTask_cli.py history
python MindTask_cli.py history --all
python MindTask_cli.py undo
```

`undo` rolls back the latest operation that has not already been undone.

## Version

```bash
python MindTask_cli.py version
```
