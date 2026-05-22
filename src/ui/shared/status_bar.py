"""Status bar helpers for page and drawer level feedback."""

from __future__ import annotations

from PySide6.QtCore import QTimer


class StatusBarMixin:
    """Mixin for status messages tied to the active page or task drawer."""

    def show_status_message(self, key: str, timeout_ms: int = 3500, **kwargs: object) -> None:
        self.statusBar().showMessage(self.tr(key, **kwargs), timeout_ms)

    def show_project_count_status(self) -> None:
        if hasattr(self, "projects_table"):
            count = getattr(self, "project_total_count", self.projects_table.rowCount())
            self.statusBar().showMessage(self.tr("project_status_count", count=count))

    def show_history_count_status(self) -> None:
        if hasattr(self, "history_drawer_table"):
            count = len(getattr(self, "history_rows", [])) or self.history_drawer_table.rowCount()
            self.statusBar().showMessage(self.tr("history_status_count", count=count))

    def show_task_count_status(self) -> None:
        if (
            hasattr(self, "tasks")
            and self._is_tasks_page()
            and not self._is_projects_drawer_open()
            and not self._is_history_drawer_open()
        ):
            self.statusBar().showMessage(self.tr("task_count", count=len(self.tasks)))

    def show_settings_status(self) -> None:
        self.statusBar().clearMessage()

    def show_project_operation_status(self, key: str, **kwargs: object) -> None:
        self.show_status_message(key, **kwargs)
        QTimer.singleShot(3500, self._restore_project_status_if_open)

    def show_history_operation_status(self, count: int) -> None:
        self.show_status_message("status_history_undone", count=count)
        QTimer.singleShot(3500, self._restore_history_status_if_open)

    def show_task_operation_status(self, key: str, **kwargs: object) -> None:
        self.show_status_message(key, **kwargs)
        QTimer.singleShot(3500, self.show_task_count_status)

    def _restore_project_status_if_open(self) -> None:
        if self._is_projects_drawer_open():
            self.show_project_count_status()

    def _restore_history_status_if_open(self) -> None:
        if self._is_history_drawer_open():
            self.show_history_count_status()
