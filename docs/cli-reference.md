# CLI Reference

Main entry point:

```bash
python MindTask_cli.py <command> [options]
```

Global option:

- `--config PATH`: use a custom MindTask config file

## Task Commands

```bash
python MindTask_cli.py add "Write report" --description "Quarterly summary" --priority high --due tomorrow
python MindTask_cli.py list --status 0 --priority 3 --detailed
python MindTask_cli.py show 1
python MindTask_cli.py update 1 --status doing
python MindTask_cli.py complete 1
python MindTask_cli.py delete 1
```

Task options:

- `--priority none|low|medium|high` or `0|1|2|3`
- `--status open|doing|done` or `0|1|2`
- `--due today|tomorrow|+N|YYYY-MM-DD|none`
- `--limit N`
- `--json`

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
