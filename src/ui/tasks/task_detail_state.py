"""Task detail draft state helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget


class TaskDetailStateMixin:
    """Manage task detail draft values and field state markers."""

    def _current_detail_values(self) -> Dict[str, object]:
        try:
            due_date = self.due_editor.due_value()
        except ValueError:
            due_date = "__invalid_due_date__"
        return {
            "title": self.title_edit.text(),
            "description": self.description_edit.toPlainText(),
            "status": self.status_combo.currentData(),
            "priority": self.priority_combo.currentData(),
            "project_id": self.project_combo.currentData(),
            "due_date": due_date,
            "due_mode": self.due_editor.due_mode(),
        }

    def _empty_detail_values(self) -> Dict[str, object]:
        due_parts = ("none", None, None)
        return {
            "title": "",
            "description": "",
            "status": 0,
            "priority": 0,
            "project_id": self._current_project_id() if hasattr(self, "project_list") else None,
            "due_date": None,
            "due_mode": "none",
            "due_mode_part": due_parts[0],
            "due_date_part": due_parts[1],
            "due_time_part": due_parts[2],
        }

    def _set_detail_original_values(self, task: Dict[str, Any]) -> None:
        due_mode = task.get("due_mode") or "none"
        due_parts = self._detail_due_parts(task.get("due_date"), due_mode)
        self._detail_original_values = {
            "title": task.get("title") or "",
            "description": task.get("description") or "",
            "status": int(task.get("status") or 0),
            "priority": int(task.get("priority") or 0),
            "project_id": task.get("project_id"),
            "due_date": task.get("due_date"),
            "due_mode": due_mode,
            "due_mode_part": due_parts[0],
            "due_date_part": due_parts[1],
            "due_time_part": due_parts[2],
        }
        self._update_detail_field_states()

    def _detail_due_parts(self, due_date: object, due_mode: str) -> tuple[str, Optional[str], Optional[str]]:
        if not due_date or due_mode == "none":
            return "none", None, None
        text = str(due_date)
        try:
            due = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            date_part = text[:10]
            time_part = text[11:].strip() if due_mode == "exact_time" and len(text) > 11 else None
            return due_mode, date_part, time_part
        date_part = due.strftime("%Y-%m-%d")
        time_part = due.strftime("%H:%M:%S") if due_mode == "exact_time" and due.second else None
        if due_mode == "exact_time" and time_part is None:
            time_part = due.strftime("%H:%M")
        return due_mode, date_part, time_part

    def _update_detail_field_states(self, *_args: object) -> None:
        if not self._detail_original_values:
            self._clear_detail_field_states()
            return
        values = self._current_detail_values()
        self._mark_detail_field(self.title_edit, values["title"] != self._detail_original_values.get("title"))
        self._mark_detail_field(self.description_edit, values["description"] != self._detail_original_values.get("description"))
        self._mark_detail_field(
            self.description_preview,
            values["description"] != self._detail_original_values.get("description"),
        )
        self._mark_detail_field(self.status_combo, values["status"] != self._detail_original_values.get("status"))
        self._mark_detail_field(self.priority_combo, values["priority"] != self._detail_original_values.get("priority"))
        self._mark_detail_field(self.project_combo, values["project_id"] != self._detail_original_values.get("project_id"))
        due_mode_part, due_date_part, due_time_part = self.due_editor.due_parts()
        self._mark_detail_field(
            self.due_editor.time_mode_combo,
            due_mode_part != self._detail_original_values.get("due_mode_part"),
        )
        self._mark_detail_field(
            self.due_editor.date_edit,
            due_date_part != self._detail_original_values.get("due_date_part"),
        )
        self._mark_detail_field(
            self.due_editor.time_combo,
            due_time_part != self._detail_original_values.get("due_time_part"),
        )
        self._set_detail_state_property(self.title_edit, "detailInvalid", not self.title_edit.text().strip())
        self._update_due_invalid_states()

    def _has_detail_changes(self) -> bool:
        if not self._detail_original_values:
            return False
        values = self._current_detail_values()
        return any(
            values.get(key) != self._detail_original_values.get(key)
            for key in ("title", "description", "status", "priority", "project_id", "due_date", "due_mode")
        )

    def _clear_detail_field_states(self) -> None:
        for widget in (
            self.title_edit,
            self.description_edit,
            self.description_preview,
            self.status_combo,
            self.priority_combo,
            self.project_combo,
            self.due_editor,
            self.due_editor.time_mode_combo,
            self.due_editor.date_edit,
            self.due_editor.time_combo,
        ):
            self._mark_detail_field(widget, False)
            self._set_detail_state_property(widget, "detailInvalid", False)

    def _mark_detail_field(self, widget: QWidget, modified: bool) -> None:
        self._set_detail_state_property(widget, "detailModified", modified)

    def _update_due_invalid_states(self) -> None:
        date_invalid, time_invalid = self.due_editor.invalid_parts()
        self._set_detail_state_property(self.due_editor.date_edit, "detailInvalid", date_invalid)
        self._set_detail_state_property(self.due_editor.time_combo, "detailInvalid", time_invalid)

    def _set_detail_state_property(self, widget: QWidget, name: str, value: bool) -> None:
        if widget.property(name) == value:
            return
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
