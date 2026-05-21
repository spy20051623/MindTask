"""Project management page for the desktop window."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..shared.dialog_helpers import confirm_question
from .project_dialog import ProjectDialog


class ProjectPageMixin:
    """Mixin for project management table layout and commands."""

    def _build_projects_page(self) -> QWidget:
        return self._build_project_management_panel()

    def _build_project_drawer(self) -> QFrame:
        panel = self._build_project_management_panel()
        panel.setObjectName("DetailPanel")
        return panel

    def _build_project_management_panel(self) -> QFrame:
        page = QFrame()
        page.setObjectName("DetailPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QWidget()
        header.setObjectName("TransparentRow")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        self.projects_title_label = self._section_label("")
        header_row.addWidget(self.projects_title_label)
        header_row.addStretch()
        self.close_projects_drawer_button = self._icon_button("", "fa6s.xmark", "X", self.close_projects_drawer)
        header_row.addWidget(self.close_projects_drawer_button)
        layout.addWidget(header)

        actions = QWidget()
        actions.setObjectName("TransparentRow")
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        self.new_project_button = QPushButton()
        self.new_project_button.clicked.connect(self.open_new_project_dialog)
        self.rename_project_button = QPushButton()
        self.rename_project_button.setObjectName("SecondaryButton")
        self.rename_project_button.clicked.connect(self.open_rename_project_dialog)
        self.delete_project_button = QPushButton()
        self.delete_project_button.setObjectName("DangerButton")
        self.delete_project_button.clicked.connect(self.delete_selected_project)
        self.project_count_label = QLabel()
        self.project_count_label.setObjectName("MutedLabel")
        actions_row.addWidget(self.new_project_button)
        actions_row.addWidget(self.rename_project_button)
        actions_row.addWidget(self.delete_project_button)
        actions_row.addStretch()
        actions_row.addWidget(self.project_count_label)
        layout.addWidget(actions)

        self.projects_table = QTableWidget(0, 5)
        self.projects_table.setObjectName("TaskTable")
        self.projects_table.setHorizontalHeaderLabels(["ID", "", "", "", ""])
        self.projects_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.projects_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.projects_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionsClickable(True)
        self.projects_table.horizontalHeader().setSortIndicatorShown(True)
        self.projects_table.horizontalHeader().sectionClicked.connect(self.sort_projects_by_column)
        self.projects_table.itemSelectionChanged.connect(self.update_project_buttons)
        layout.addWidget(self.projects_table, 1)
        return page

    def refresh_project_table(self) -> None:
        if not hasattr(self, "projects_table"):
            return
        selected_id = self._selected_project_management_id()
        projects = self._sort_projects(self.db.get_project_summaries())
        self.projects_table.setRowCount(len(projects))
        for row, project in enumerate(projects):
            values = [
                project["id"],
                project["name"],
                project["task_count"],
                project["active_task_count"],
                project["completed_task_count"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self._apply_plain_cell_color(item, row)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, project["id"])
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column in {2, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.projects_table.setItem(row, column, item)
        self.projects_table.resizeRowsToContents()
        self.project_count_label.setText(self.tr("project_count", count=len(projects)))
        if self._is_projects_drawer_open():
            self.show_project_count_status()
        if selected_id is not None:
            self._select_project_management_row(selected_id)
        elif projects:
            self.projects_table.selectRow(0)
        self.update_project_buttons()

    def sort_projects_by_column(self, column: int) -> None:
        if column == self.project_sort_column:
            self.project_sort_order = (
                Qt.SortOrder.DescendingOrder
                if self.project_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self.project_sort_column = column
            self.project_sort_order = Qt.SortOrder.AscendingOrder
        self._update_project_sort_indicator()
        self.refresh_project_table()

    def _update_project_sort_indicator(self) -> None:
        if hasattr(self, "projects_table"):
            self.projects_table.horizontalHeader().setSortIndicator(self.project_sort_column, self.project_sort_order)

    def _sort_projects(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        reverse = self.project_sort_order == Qt.SortOrder.DescendingOrder

        def value_for(project: Dict[str, Any]) -> Any:
            if self.project_sort_column == 0:
                return project.get("id")
            if self.project_sort_column == 1:
                return (project.get("name") or "").casefold()
            if self.project_sort_column == 2:
                return project.get("task_count")
            if self.project_sort_column == 3:
                return project.get("active_task_count")
            if self.project_sort_column == 4:
                return project.get("completed_task_count")
            return project.get("id")

        return sorted(projects, key=lambda project: (value_for(project), project.get("id") or 0), reverse=reverse)

    def open_new_project_dialog(self) -> None:
        dialog = ProjectDialog(language=self.language, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.project_name()
        try:
            project_id = self.db.create_project(name)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_project"), str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_create_failed", error=exc))
            return
        self.refresh_all()
        self._select_project_management_row(project_id)
        self.show_project_operation_status("status_project_created", name=name)

    def open_rename_project_dialog(self) -> None:
        project_id = self._selected_project_management_id()
        if project_id is None:
            QMessageBox.information(self, self.tr("project"), self.tr("select_project_first"))
            return
        project = self.db.get_project(project_id)
        if not project:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_not_found"))
            self.refresh_all()
            return
        dialog = ProjectDialog(project["name"], self.language, parent=self)
        dialog.setWindowTitle(self.tr("rename_project"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        old_name = project["name"]
        new_name = dialog.project_name()
        try:
            changed = self.db.update_project(project_id, name=new_name)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_project"), str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_rename_failed", error=exc))
            return
        if not changed:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_not_found"))
            return
        self.refresh_all()
        self._select_project_management_row(project_id)
        self.show_project_operation_status("status_project_renamed", old=old_name, new=new_name)

    def delete_selected_project(self) -> None:
        project_id = self._selected_project_management_id()
        if project_id is None:
            QMessageBox.information(self, self.tr("project"), self.tr("select_project_first"))
            return
        project = self.db.get_project(project_id)
        if not project:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_not_found"))
            self.refresh_all()
            return
        if not confirm_question(
            self,
            self.tr("delete_project"),
            self.tr("delete_project_confirm", name=project["name"]),
            self.translator,
        ):
            return
        try:
            deleted = self.db.delete_project(project_id)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("delete_project"), str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_delete_failed", error=exc))
            return
        if not deleted:
            QMessageBox.warning(self, self.tr("project"), self.tr("project_not_found"))
            return
        self.refresh_all()
        self.show_project_operation_status("status_project_deleted", name=project["name"])

    def _selected_project_management_id(self) -> Optional[int]:
        if not hasattr(self, "projects_table"):
            return None
        rows = self.projects_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.projects_table.item(rows[0].row(), 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _selected_project_task_count(self) -> int:
        rows = self.projects_table.selectionModel().selectedRows()
        if not rows:
            return 0
        item = self.projects_table.item(rows[0].row(), 2)
        return int(item.text()) if item is not None and item.text().isdigit() else 0

    def _select_project_management_row(self, project_id: int) -> None:
        for row in range(self.projects_table.rowCount()):
            if self.projects_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == project_id:
                self.projects_table.selectRow(row)
                return

    def update_project_buttons(self) -> None:
        has_selection = self._selected_project_management_id() is not None
        self.rename_project_button.setEnabled(has_selection)
        self.delete_project_button.setEnabled(has_selection)
