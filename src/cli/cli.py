#!/usr/bin/env python3
"""Command-line interface for MindTask."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .. import __version__
from ..core import MindTaskDB


PRIORITY_NAMES = {0: "None", 1: "Low", 2: "Medium", 3: "High"}
STATUS_NAMES = {0: "Open", 1: "Doing", 2: "Done"}
PRIORITY_INPUT = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
}
STATUS_INPUT = {"open": 0, "doing": 1, "done": 2, "0": 0, "1": 1, "2": 2}


class MindTaskCLI:
    """Command dispatcher for the MindTask CLI."""

    def __init__(self, config_path: Optional[str] = None):
        self.db = MindTaskDB(config_path=config_path)

    def list_projects(self, args: argparse.Namespace) -> int:
        projects = self.db.get_projects()
        if not projects:
            print("No projects found.")
            return 0

        for project in projects:
            print(f"[{project['id']}] {project['name']}  {project.get('description') or ''}")
        return 0

    def create_project(self, args: argparse.Namespace) -> int:
        project_id = self.db.create_project(args.name, args.description or "", args.color)
        print(f"Created project #{project_id}: {args.name}")
        return 0

    def list_tasks(self, args: argparse.Namespace) -> int:
        tasks = self.db.get_tasks(
            project_id=args.project,
            status=args.status,
            priority=args.priority,
            limit=args.limit or self.db.config.default_task_limit,
        )
        if args.json:
            print(json.dumps(tasks, ensure_ascii=False, indent=2))
        else:
            self._print_tasks(tasks, detailed=args.detailed)
        return 0

    def add_task(self, args: argparse.Namespace) -> int:
        task_id = self.db.create_task(
            title=args.title,
            description=args.description or "",
            project_id=args.project,
            priority=parse_priority(args.priority),
            due_date=parse_due_date(args.due),
        )
        print(f"Created task #{task_id}: {args.title}")
        return 0

    def update_task(self, args: argparse.Namespace) -> int:
        updates: Dict[str, Any] = {}
        if args.title is not None:
            updates["title"] = args.title
        if args.description is not None:
            updates["description"] = args.description
        if args.project is not None:
            updates["project_id"] = args.project
        if args.priority is not None:
            updates["priority"] = parse_priority(args.priority)
        if args.status is not None:
            updates["status"] = parse_status(args.status)
        if args.due is not None:
            updates["due_date"] = None if args.due.lower() == "none" else parse_due_date(args.due)

        if not updates:
            print("No fields provided.")
            return 1

        if not self.db.update_task(args.task_id, **updates):
            print(f"Task #{args.task_id} was not found, or no supported fields were provided.")
            return 1

        print(f"Updated task #{args.task_id}.")
        return 0

    def complete_task(self, args: argparse.Namespace) -> int:
        if self.db.complete_task(args.task_id):
            print(f"Completed task #{args.task_id}.")
            return 0
        print(f"Task #{args.task_id} was not found.")
        return 1

    def delete_task(self, args: argparse.Namespace) -> int:
        task = self.db.get_task(args.task_id)
        if not task:
            print(f"Task #{args.task_id} was not found.")
            return 1

        if not args.yes:
            confirm = input(f"Delete '{task['title']}'? Type yes: ")
            if confirm.lower() != "yes":
                print("Canceled.")
                return 0

        if self.db.delete_task(args.task_id):
            print(f"Deleted task #{args.task_id}.")
            return 0
        print("Delete failed.")
        return 1

    def show_task(self, args: argparse.Namespace) -> int:
        task = self.db.get_task(args.task_id)
        if not task:
            print(f"Task #{args.task_id} was not found.")
            return 1
        print(json.dumps(task, ensure_ascii=False, indent=2))
        return 0

    def stats(self, args: argparse.Namespace) -> int:
        stats = self.db.get_stats()
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            return 0

        total = stats.get("total_tasks", 0)
        completed = stats.get("completed_tasks", 0)
        pending = stats.get("pending_tasks", 0)
        rate = (completed / total * 100) if total else 0
        print("MindTask stats")
        print(f"Total: {total}")
        print(f"Completed: {completed}")
        print(f"Pending: {pending}")
        print(f"Completion rate: {rate:.1f}%")
        print(f"Upcoming in 3 days: {stats.get('upcoming_tasks', 0)}")
        return 0

    def search(self, args: argparse.Namespace) -> int:
        tasks = self.db.search_tasks(args.keyword, args.limit or self.db.config.default_search_limit)
        if args.json:
            print(json.dumps(tasks, ensure_ascii=False, indent=2))
        else:
            self._print_tasks(tasks, detailed=args.detailed)
        return 0

    def export_tasks(self, args: argparse.Namespace) -> int:
        tasks = self.db.get_tasks(limit=args.limit)
        if args.format == "json":
            output = json.dumps(tasks, ensure_ascii=False, indent=2)
        else:
            output = self._tasks_to_csv(tasks)

        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="") as fh:
                fh.write(output)
            print(f"Exported to {args.output}")
        else:
            print(output)
        return 0

    def history(self, args: argparse.Namespace) -> int:
        rows = self.db.get_history(limit=args.limit, include_undone=args.all)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0

        if not rows:
            print("No history found.")
            return 0

        for row in rows:
            status = " undone" if row.get("undone_at") else ""
            entity_id = f"#{row['entity_id']}" if row.get("entity_id") is not None else ""
            print(
                f"[{row['id']}] {row['created_at']} {row['action']} "
                f"{row['entity_type']}{entity_id}{status}"
            )
        return 0

    def undo(self, args: argparse.Namespace) -> int:
        history = self.db.undo_last_operation()
        if not history:
            print("No operation to undo.")
            return 0

        entity_id = f"#{history['entity_id']}" if history.get("entity_id") is not None else ""
        print(f"Undid [{history['id']}] {history['action']} {history['entity_type']}{entity_id}.")
        return 0

    def version(self, args: argparse.Namespace) -> int:
        print(__version__)
        return 0

    def _print_tasks(self, tasks: List[Dict[str, Any]], detailed: bool = False) -> None:
        if not tasks:
            print("No tasks found.")
            return

        for task in tasks:
            print(
                f"[{task['id']}] {task['title']} "
                f"status={task.get('status_text') or STATUS_NAMES.get(task.get('status'))} "
                f"priority={task.get('priority_text') or PRIORITY_NAMES.get(task.get('priority'))}"
            )
            if detailed:
                print(f"  project: {task.get('project_name') or ''}")
                print(f"  due: {task.get('due_date') or ''}")
                print(f"  description: {task.get('description') or ''}")

    def _tasks_to_csv(self, tasks: List[Dict[str, Any]]) -> str:
        stream = io.StringIO()
        fieldnames = [
            "id",
            "title",
            "description",
            "project_name",
            "priority_text",
            "status_text",
            "due_date",
            "created_at",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for task in tasks:
            writer.writerow({field: task.get(field, "") for field in fieldnames})
        return stream.getvalue()

def parse_priority(value: str) -> int:
    try:
        return PRIORITY_INPUT[value.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported priority: {value}") from exc


def parse_status(value: str) -> int:
    try:
        return STATUS_INPUT[value.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported status: {value}") from exc


def parse_due_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    lower = value.lower()
    now = datetime.now()
    if lower == "today":
        due = now
    elif lower == "tomorrow":
        due = now + timedelta(days=1)
    elif lower.startswith("+"):
        due = now + timedelta(days=int(lower[1:]))
    else:
        due = datetime.fromisoformat(value.replace(" ", "T"))

    return due.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MindTask command-line tool")
    parser.add_argument("--config", help="Path to the MindTask config file")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--project", type=int)
    list_parser.add_argument("--status", type=int, choices=[0, 1, 2])
    list_parser.add_argument("--priority", type=int, choices=[0, 1, 2, 3])
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--detailed", action="store_true")
    list_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("projects", help="List projects")

    project_parser = subparsers.add_parser("project-add", help="Create a project")
    project_parser.add_argument("name")
    project_parser.add_argument("--description")
    project_parser.add_argument("--color", default="#007BFF")

    add_parser = subparsers.add_parser("add", help="Create a task")
    add_parser.add_argument("title")
    add_parser.add_argument("-d", "--description")
    add_parser.add_argument("-p", "--project", type=int)
    add_parser.add_argument("--priority", default="medium")
    add_parser.add_argument("--due")

    update_parser = subparsers.add_parser("update", help="Update a task")
    update_parser.add_argument("task_id", type=int)
    update_parser.add_argument("--title")
    update_parser.add_argument("--description")
    update_parser.add_argument("--project", type=int)
    update_parser.add_argument("--priority")
    update_parser.add_argument("--status")
    update_parser.add_argument("--due")

    complete_parser = subparsers.add_parser("complete", help="Complete a task")
    complete_parser.add_argument("task_id", type=int)

    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", type=int)
    delete_parser.add_argument("-y", "--yes", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show a task")
    show_parser.add_argument("task_id", type=int)

    stats_parser = subparsers.add_parser("stats", help="Show stats")
    stats_parser.add_argument("--json", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search tasks")
    search_parser.add_argument("keyword")
    search_parser.add_argument("--limit", type=int)
    search_parser.add_argument("--detailed", action="store_true")
    search_parser.add_argument("--json", action="store_true")

    export_parser = subparsers.add_parser("export", help="Export tasks")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.add_argument("--output")
    export_parser.add_argument("--limit", type=int, default=1000)

    history_parser = subparsers.add_parser("history", help="Show operation history")
    history_parser.add_argument("--limit", type=int, default=50)
    history_parser.add_argument("--all", action="store_true", help="Include already undone operations")
    history_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("undo", help="Undo the last operation")
    subparsers.add_parser("version", help="Show the MindTask version")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cli = MindTaskCLI(args.config)
    handlers = {
        "list": cli.list_tasks,
        "projects": cli.list_projects,
        "project-add": cli.create_project,
        "add": cli.add_task,
        "update": cli.update_task,
        "complete": cli.complete_task,
        "delete": cli.delete_task,
        "show": cli.show_task,
        "stats": cli.stats,
        "search": cli.search,
        "export": cli.export_tasks,
        "history": cli.history,
        "undo": cli.undo,
        "version": cli.version,
    }

    try:
        return handlers[args.command](args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
