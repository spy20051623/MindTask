"""Task due date filtering and presentation helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from ..shared.alert_message import ALERT_DANGER, ALERT_WARN
from ..shared.style import THEME_DARK, colors_for_theme, resolve_theme


TASK_VIEW_TODAY = "__today__"
TASK_VIEW_TOMORROW = "__tomorrow__"
TASK_VIEW_THREE_DAYS = "__three_days__"
TASK_VIEW_SEVEN_DAYS = "__seven_days__"


class TaskDueMixin:
    """Handle due date filters, alerts, and due cell presentation."""

    def _format_task_due(self, task: Dict[str, Any]) -> str:
        due_date = task.get("due_date")
        if not due_date:
            return ""
        if task.get("due_mode") == "all_day":
            return f"{str(due_date)[:10]} {self.tr('all_day')}"
        return str(due_date)

    def _filter_due_tasks(self, tasks: List[Dict[str, Any]], task_view: str) -> List[Dict[str, Any]]:
        today = date.today()
        cutoff = self._due_filter_cutoff(today, task_view)
        if cutoff is None:
            return tasks
        filtered = []
        for task in tasks:
            due_date = self._task_due_date(task)
            if due_date is None:
                continue
            if task.get("status") == 3:
                continue
            if due_date <= cutoff:
                filtered.append(task)
        return filtered

    def _due_filter_cutoff(self, today: date, task_view: str) -> Optional[date]:
        if task_view == TASK_VIEW_TODAY:
            return today
        if task_view == TASK_VIEW_TOMORROW:
            return today + timedelta(days=1)
        if task_view == TASK_VIEW_THREE_DAYS:
            return today + timedelta(days=3)
        if task_view == TASK_VIEW_SEVEN_DAYS:
            return today + timedelta(days=7)
        return None

    def _task_due_date(self, task: Dict[str, Any]) -> Optional[date]:
        due_date = task.get("due_date")
        if not due_date:
            return None
        try:
            return datetime.strptime(str(due_date), "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            return None

    def _is_task_overdue(self, task: Dict[str, Any]) -> bool:
        if task.get("status") == 3:
            return False
        due_date = task.get("due_date")
        if not due_date:
            return False
        if task.get("due_mode") == "all_day":
            task_due_date = self._task_due_date(task)
            return task_due_date is not None and task_due_date < date.today()
        try:
            task_due_at = datetime.strptime(str(due_date), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return False
        return task_due_at < datetime.now()

    def _task_due_alert(self, task: Dict[str, Any]) -> Optional[tuple[int, str]]:
        if task.get("status") == 3:
            return None
        due_date = task.get("due_date")
        if not due_date:
            return None
        if task.get("due_mode") == "all_day":
            task_due_date = self._task_due_date(task)
            if task_due_date is None:
                return None
            days = (task_due_date - date.today()).days
            if days < 0:
                return ALERT_DANGER, self.tr("due_alert_overdue")
            if days == 0:
                return ALERT_DANGER, self.tr("due_alert_today")
            if days <= 3:
                return ALERT_WARN, self.tr("due_alert_days_left", days=days)
            return None
        try:
            task_due_at = datetime.strptime(str(due_date), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        remaining = task_due_at - datetime.now()
        if remaining.total_seconds() < 0:
            return ALERT_DANGER, self.tr("due_alert_overdue")
        if remaining < timedelta(hours=24):
            total_minutes = max(1, ceil(remaining.total_seconds() / 60))
            hours, minutes = divmod(total_minutes, 60)
            return ALERT_DANGER, self.tr("due_alert_time_left", hours=hours, minutes=minutes)
        task_due_date = self._task_due_date(task)
        if task_due_date is None:
            return None
        days = (task_due_date - date.today()).days
        if 1 <= days <= 3:
            return ALERT_WARN, self.tr("due_alert_days_left", days=days)
        return None

    def _format_detail_timestamp(self, value: object) -> str:
        if not value:
            return ""
        text = str(value)
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return text

    def _apply_overdue_cell_color(self, item: QTableWidgetItem) -> None:
        resolved_theme = resolve_theme(self.theme, QApplication.instance())
        colors = colors_for_theme(self.theme, QApplication.instance())
        if resolved_theme == THEME_DARK:
            item.setBackground(QColor("#4a2424"))
            item.setForeground(QColor("#fee2e2"))
        else:
            item.setBackground(QColor("#fee2e2"))
            item.setForeground(QColor(colors["text"]))
