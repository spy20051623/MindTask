"""Task list sorting helpers."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt


class TaskSortingMixin:
    """Sort tasks using either the active table column or smart task rules."""

    def _sort_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if getattr(self, "smart_task_sorting", True):
            return sorted(tasks, key=cmp_to_key(self._compare_smart_tasks))
        return self._sort_tasks_by_selected_column(tasks)

    def _sort_tasks_by_selected_column(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        reverse = self.task_sort_order == Qt.SortOrder.DescendingOrder
        present = [task for task in tasks if self._task_sort_column_value(task) not in {None, ""}]
        missing = [task for task in tasks if self._task_sort_column_value(task) in {None, ""}]
        return sorted(present, key=self._task_sort_column_value, reverse=reverse) + sorted(
            missing,
            key=lambda task: task.get("id") or 0,
        )

    def _compare_smart_tasks(self, left: Dict[str, Any], right: Dict[str, Any]) -> int:
        left_completed = self._task_completed(left)
        right_completed = self._task_completed(right)
        if left_completed != right_completed:
            return 1 if left_completed else -1

        if left_completed:
            result = self._compare_values(
                left.get("completed_at"),
                right.get("completed_at"),
                descending=True,
            )
        else:
            result = self._compare_values(
                self._task_due_day(left),
                self._task_due_day(right),
            )
            if result == 0:
                result = self._compare_values(
                    left.get("priority") or 0,
                    right.get("priority") or 0,
                    descending=True,
                    missing_last=False,
                )

        if result != 0:
            return result

        result = self._compare_selected_task_column(left, right)
        if result != 0:
            return result
        return self._compare_values(left.get("id"), right.get("id"), missing_last=False)

    def _task_completed(self, task: Dict[str, Any]) -> bool:
        return int(task.get("status") or 0) == 3

    def _task_due_day(self, task: Dict[str, Any]) -> Optional[str]:
        due_date = task.get("due_date")
        if not due_date:
            return None
        return str(due_date)[:10]

    def _compare_selected_task_column(self, left: Dict[str, Any], right: Dict[str, Any]) -> int:
        return self._compare_values(
            self._task_sort_column_value(left),
            self._task_sort_column_value(right),
            descending=self.task_sort_order == Qt.SortOrder.DescendingOrder,
        )

    def _task_sort_column_value(self, task: Dict[str, Any]) -> Any:
        if self.task_sort_column == 0:
            return task.get("id")
        if self.task_sort_column == 1:
            return (task.get("title") or "").casefold()
        if self.task_sort_column == 2:
            return task.get("status")
        if self.task_sort_column == 3:
            return task.get("priority")
        if self.task_sort_column == 4:
            return (task.get("project_name") or "").casefold()
        if self.task_sort_column == 5:
            return task.get("due_date")
        return task.get("id")

    def _compare_values(
        self,
        left: Any,
        right: Any,
        *,
        descending: bool = False,
        missing_last: bool = True,
    ) -> int:
        left_missing = left in {None, ""}
        right_missing = right in {None, ""}
        if left_missing or right_missing:
            if left_missing == right_missing:
                return 0
            if missing_last:
                return 1 if left_missing else -1
            return -1 if left_missing else 1
        if left == right:
            return 0
        if left < right:
            return 1 if descending else -1
        return -1 if descending else 1
