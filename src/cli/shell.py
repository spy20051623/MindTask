#!/usr/bin/env python3
"""Interactive shell for MindTask."""

from __future__ import annotations

import cmd
import json
import shlex
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .. import __version__
from ..core import MindTaskDB


class MindTaskShell(cmd.Cmd):
    intro = (
        "\nMindTask Shell\n"
        "Type 'help' to list commands, or 'exit' to quit.\n"
    )
    prompt = "MindTask> "

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.db = MindTaskDB(config_path=config_path)

    def do_projects(self, arg: str) -> None:
        """List projects."""
        projects = self.db.get_projects()
        if not projects:
            print("No projects found.")
            return

        for project in projects:
            print(f"[{project['id']}] {project['name']} - {project.get('description') or ''}")

    def do_list(self, arg: str) -> None:
        """List tasks: list [status=0|1|2] [priority=0|1|2|3] [project=ID] [limit=N]."""
        args = self._parse_key_values(arg)
        tasks = self.db.get_tasks(
            project_id=self._optional_int(args.get("project")),
            status=self._optional_int(args.get("status")),
            priority=self._optional_int(args.get("priority")),
            limit=int(args.get("limit", self.db.config.default_task_limit)),
        )
        self._print_tasks(tasks)

    def do_add(self, arg: str) -> None:
        """Add a task: add "title" [description="text"] [project=ID] [priority=0-3] [due=today|tomorrow|+3|YYYY-MM-DD]."""
        if not arg.strip():
            print('Usage: add "title" [description="text"] [project=ID] [priority=0-3] [due=today|tomorrow|+3|YYYY-MM-DD]')
            return

        try:
            parts = shlex.split(arg)
            title = parts[0]
            args = self._parse_key_values(" ".join(parts[1:]))
            task_id = self.db.create_task(
                title=title,
                description=args.get("description", ""),
                project_id=self._optional_int(args.get("project")),
                priority=int(args.get("priority", 2)),
                due_date=self._parse_due_date(args.get("due")),
            )
            print(f"Created task #{task_id}: {title}")
        except Exception as exc:
            print(f"Error: {exc}")

    def do_update(self, arg: str) -> None:
        """Update a task: update ID [title="text"] [description="text"] [priority=0-3] [status=0-2] [due=YYYY-MM-DD|none]."""
        try:
            parts = shlex.split(arg)
            if not parts:
                print('Usage: update ID [title="text"] [description="text"] [priority=0-3] [status=0-2] [due=YYYY-MM-DD|none]')
                return

            task_id = int(parts[0])
            args = self._parse_key_values(" ".join(parts[1:]))
            updates = self._task_updates(args)
            if not updates:
                print("No supported fields provided.")
                return

            if self.db.update_task(task_id, **updates):
                print(f"Updated task #{task_id}.")
            else:
                print(f"Task #{task_id} was not found.")
        except Exception as exc:
            print(f"Error: {exc}")

    def do_complete(self, arg: str) -> None:
        """Complete a task: complete ID."""
        try:
            task_id = int(arg.strip())
            print("Completed." if self.db.complete_task(task_id) else f"Task #{task_id} was not found.")
        except ValueError:
            print("Usage: complete ID")

    def do_delete(self, arg: str) -> None:
        """Delete a task: delete ID."""
        try:
            task_id = int(arg.strip())
            task = self.db.get_task(task_id)
            if not task:
                print(f"Task #{task_id} was not found.")
                return
            confirm = input(f"Delete '{task['title']}'? Type yes: ")
            if confirm.lower() != "yes":
                print("Canceled.")
                return
            print("Deleted." if self.db.delete_task(task_id) else "Delete failed.")
        except ValueError:
            print("Usage: delete ID")

    def do_show(self, arg: str) -> None:
        """Show one task: show ID."""
        try:
            task = self.db.get_task(int(arg.strip()))
            print(json.dumps(task, ensure_ascii=False, indent=2) if task else "Task was not found.")
        except ValueError:
            print("Usage: show ID")

    def do_stats(self, arg: str) -> None:
        """Show statistics."""
        stats = self.db.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    def do_search(self, arg: str) -> None:
        """Search tasks: search keyword [limit=N]."""
        args = self._parse_key_values(arg)
        keyword = args.pop("keyword", None)
        if not keyword:
            print("Usage: search keyword [limit=N]")
            return
        tasks = self.db.search_tasks(keyword, int(args.get("limit", self.db.config.default_search_limit)))
        self._print_tasks(tasks)

    def do_history(self, arg: str) -> None:
        """Show operation history: history [limit=N] [all=true]."""
        args = self._parse_key_values(arg)
        include_undone = args.get("all", "").lower() in {"1", "true", "yes"}
        rows = self.db.get_history(limit=int(args.get("limit", 50)), include_undone=include_undone)
        if not rows:
            print("No history found.")
            return
        for row in rows:
            status = " undone" if row.get("undone_at") else ""
            entity_id = f"#{row['entity_id']}" if row.get("entity_id") is not None else ""
            print(f"[{row['id']}] {row['created_at']} {row['action']} {row['entity_type']}{entity_id}{status}")

    def do_undo(self, arg: str) -> None:
        """Undo the last operation."""
        history = self.db.undo_last_operation()
        if not history:
            print("No operation to undo.")
            return
        entity_id = f"#{history['entity_id']}" if history.get("entity_id") is not None else ""
        print(f"Undid [{history['id']}] {history['action']} {history['entity_type']}{entity_id}.")

    def do_version(self, arg: str) -> None:
        """Show the MindTask version."""
        print(__version__)

    def do_exit(self, arg: str) -> bool:
        """Exit the shell."""
        print("Bye.")
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit the shell."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:
        """Exit on Ctrl-D."""
        print()
        return self.do_exit(arg)

    def emptyline(self) -> None:
        pass

    def _parse_key_values(self, arg: str) -> Dict[str, str]:
        args: Dict[str, str] = {}
        for part in shlex.split(arg):
            if "=" in part:
                key, value = part.split("=", 1)
                args[key] = value
            elif "keyword" not in args:
                args["keyword"] = part
        return args

    def _task_updates(self, args: Dict[str, str]) -> Dict[str, Any]:
        updates: Dict[str, Any] = {}
        if "title" in args:
            updates["title"] = args["title"]
        if "description" in args:
            updates["description"] = args["description"]
        if "project" in args:
            updates["project_id"] = self._optional_int(args["project"])
        if "priority" in args:
            updates["priority"] = int(args["priority"])
        if "status" in args:
            updates["status"] = int(args["status"])
        if "due" in args:
            updates["due_date"] = None if args["due"].lower() == "none" else self._parse_due_date(args["due"])
        return updates

    def _parse_due_date(self, due: Optional[str]) -> Optional[str]:
        if not due:
            return None
        due = due.lower()
        now = datetime.now()
        if due == "today":
            value = now
        elif due == "tomorrow":
            value = now + timedelta(days=1)
        elif due.startswith("+"):
            value = now + timedelta(days=int(due[1:]))
        else:
            value = datetime.fromisoformat(due.replace(" ", "T"))
        return value.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")

    def _optional_int(self, value: Optional[str]) -> Optional[int]:
        return int(value) if value not in (None, "") else None

    def _print_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        if not tasks:
            print("No tasks found.")
            return

        for task in tasks:
            due = f" due={task['due_date']}" if task.get("due_date") else ""
            project = f" project={task['project_name']}" if task.get("project_name") else ""
            print(
                f"[{task['id']}] {task['title']}"
                f" status={task.get('status_text')}"
                f" priority={task.get('priority_text')}"
                f"{project}{due}"
            )

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="MindTask interactive shell")
    parser.add_argument("--config", help="Path to the MindTask config file")
    args = parser.parse_args()

    MindTaskShell(args.config).cmdloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
