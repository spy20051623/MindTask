"""Main desktop window for MindTask."""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import MindTaskDB, get_config_path, normalize_due_date, save_database_path, save_ui_theme
from .style import THEME_OPTIONS, THEME_SYSTEM, badge_colors_for_theme, build_app_style, colors_for_theme

try:
    import qtawesome as qta
except ModuleNotFoundError:
    qta = None


STATUS_LABELS = {
    0: "not_started",
    1: "in_progress",
    2: "suspended",
    3: "completed",
}
STATUS_VALUES = {value: key for key, value in STATUS_LABELS.items()}
PRIORITY_LABELS = {
    0: "None",
    1: "Low",
    2: "Medium",
    3: "High",
}


def required_label(text: str) -> QLabel:
    label = QLabel(f'{text} <span style="color:#dc2626;">*</span>')
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


class MindTaskWindow(QMainWindow):
    """Task-focused desktop shell around the existing MindTask core."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = str(get_config_path(config_path))
        self.db = MindTaskDB(config_path=config_path)
        self.tasks: List[Dict[str, Any]] = []
        self.selected_task_id: Optional[int] = None
        self.theme = self.db.config.ui_theme
        self._apply_theme_to_app(self.theme)

        self.setWindowTitle("MindTask")
        self.resize(1180, 720)

        self._build_layout()
        self.refresh_all()

    def _build_layout(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.page_stack = QStackedWidget()
        self.tasks_page = self._build_tasks_page()
        self.projects_page = self._build_projects_page()
        self.settings_page = self._build_settings_page()
        self.page_stack.addWidget(self.tasks_page)
        self.page_stack.addWidget(self.projects_page)
        self.page_stack.addWidget(self.settings_page)
        layout.addWidget(self.page_stack, 1)
        layout.addWidget(self._build_bottom_navigation())
        self.setCentralWidget(root)

        self.setStatusBar(QStatusBar())

    def _build_bottom_navigation(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("BottomNav")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.tasks_nav_button = QPushButton("Tasks")
        self.tasks_nav_button.setObjectName("NavButtonActive")
        self.tasks_nav_button.clicked.connect(lambda: self.switch_page(0))
        self.projects_nav_button = QPushButton("Projects")
        self.projects_nav_button.setObjectName("NavButton")
        self.projects_nav_button.clicked.connect(lambda: self.switch_page(1))
        self.settings_nav_button = QPushButton("Settings")
        self.settings_nav_button.setObjectName("NavButton")
        self.settings_nav_button.clicked.connect(lambda: self.switch_page(2))

        layout.addStretch()
        layout.addWidget(self.tasks_nav_button)
        layout.addWidget(self.projects_nav_button)
        layout.addWidget(self.settings_nav_button)
        layout.addStretch()
        return panel

    def _build_tasks_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_task_table())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([220, 620, 340])
        return splitter

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("Projects"))
        self.project_list = QListWidget()
        self.project_list.setObjectName("ProjectList")
        self.project_list.currentItemChanged.connect(lambda _current, _previous: self.refresh_tasks())
        layout.addWidget(self.project_list)

        return panel

    def _build_task_table(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        actions = QFrame()
        actions.setObjectName("TaskActions")
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchInput")
        self.search_edit.setPlaceholderText("Search tasks")
        self.search_edit.returnPressed.connect(self.refresh_tasks)
        actions_row.addWidget(self.search_edit, 1)

        self.add_button = self._icon_button(
            "New task",
            "fa6s.plus",
            "New",
            self.open_new_task_dialog,
        )
        actions_row.addWidget(self.add_button)

        self.refresh_button = self._icon_button(
            "Refresh",
            "fa6s.arrows-rotate",
            "Ref",
            self.refresh_all,
        )
        actions_row.addWidget(self.refresh_button)

        self.history_button = self._icon_button(
            "History",
            "fa6s.clock-rotate-left",
            "His",
            self.open_history_dialog,
        )
        actions_row.addWidget(self.history_button)
        layout.addWidget(actions)

        header = QWidget()
        header.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.addWidget(self._section_label("Tasks"))
        self.task_count_label = QLabel("0 tasks")
        self.task_count_label.setObjectName("MutedLabel")
        header_row.addStretch()
        header_row.addWidget(self.task_count_label)
        layout.addWidget(header)

        self.task_table = QTableWidget(0, 6)
        self.task_table.setObjectName("TaskTable")
        self.task_table.setHorizontalHeaderLabels(["ID", "Title", "Status", "Priority", "Project", "Due"])
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.itemSelectionChanged.connect(self.load_selected_task)

        self.empty_label = QLabel("No tasks")
        self.empty_label.setObjectName("EmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.task_stack = QStackedWidget()
        self.task_stack.addWidget(self.task_table)
        self.task_stack.addWidget(self.empty_label)
        layout.addWidget(self.task_stack, 1)

        return panel

    def _themed_icon(self, name: str) -> QIcon:
        if qta is None:
            return QIcon()
        colors = colors_for_theme(self.theme, QApplication.instance())
        old_local_appdata = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = ""
        try:
            return qta.icon(name, color=colors["text"])
        except Exception:
            return QIcon()
        finally:
            if old_local_appdata is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local_appdata

    def _icon_button(self, tooltip: str, icon_name: str, fallback_text: str, handler: Any) -> QPushButton:
        button = QPushButton()
        button.setObjectName("IconButton")
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(34, 34)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        self._set_action_button_icon(button, icon_name, fallback_text)
        button.clicked.connect(handler)
        return button

    def _set_action_button_icon(self, button: QPushButton, icon_name: str, fallback_text: str) -> None:
        icon = self._themed_icon(icon_name)
        if icon.isNull():
            button.setIcon(QIcon())
            button.setText(fallback_text)
            return
        button.setText("")
        button.setIcon(icon)

    def _refresh_action_icons(self) -> None:
        if not hasattr(self, "add_button"):
            return
        self._set_action_button_icon(self.add_button, "fa6s.plus", "New")
        self._set_action_button_icon(self.refresh_button, "fa6s.arrows-rotate", "Ref")
        self._set_action_button_icon(self.history_button, "fa6s.clock-rotate-left", "His")

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("Task Detail"))

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.status_combo = QComboBox()
        self.priority_combo = QComboBox()
        self.project_combo = QComboBox()
        self.due_edit = QLineEdit()
        self.due_edit.setPlaceholderText("YYYY-MM-DD HH:MM:SS")

        for status in STATUS_LABELS.values():
            self.status_combo.addItem(status)
        for priority, label in PRIORITY_LABELS.items():
            self.priority_combo.addItem(label, priority)

        form = QFormLayout()
        form.addRow(required_label("Title"), self.title_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Status", self.status_combo)
        form.addRow("Priority", self.priority_combo)
        form.addRow("Project", self.project_combo)
        form.addRow("Due", self.due_edit)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.save_selected_task)
        complete_button = QPushButton("Complete")
        complete_button.setObjectName("SecondaryButton")
        complete_button.clicked.connect(self.complete_selected_task)
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("DangerButton")
        delete_button.clicked.connect(self.delete_selected_task)
        button_row.addWidget(save_button)
        button_row.addWidget(complete_button)
        button_row.addWidget(delete_button)
        layout.addLayout(button_row)

        layout.addStretch()
        return panel

    def _build_projects_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        header_row.addWidget(self._section_label("Projects"))
        self.project_count_label = QLabel("0 projects")
        self.project_count_label.setObjectName("MutedLabel")
        header_row.addStretch()
        header_row.addWidget(self.project_count_label)

        self.new_project_button = QPushButton("New Project")
        self.new_project_button.clicked.connect(self.open_new_project_dialog)
        self.rename_project_button = QPushButton("Rename")
        self.rename_project_button.setObjectName("SecondaryButton")
        self.rename_project_button.clicked.connect(self.open_rename_project_dialog)
        self.delete_project_button = QPushButton("Delete")
        self.delete_project_button.setObjectName("DangerButton")
        self.delete_project_button.clicked.connect(self.delete_selected_project)
        header_row.addWidget(self.new_project_button)
        header_row.addWidget(self.rename_project_button)
        header_row.addWidget(self.delete_project_button)
        layout.addWidget(header)

        self.projects_table = QTableWidget(0, 5)
        self.projects_table.setObjectName("TaskTable")
        self.projects_table.setHorizontalHeaderLabels(["ID", "Name", "Tasks", "Active", "Completed"])
        self.projects_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.projects_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.projects_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.projects_table.itemSelectionChanged.connect(self.update_project_buttons)
        layout.addWidget(self.projects_table, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(self._section_label("Settings"))

        form_panel = QFrame()
        form_panel.setObjectName("DetailPanel")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        form = QFormLayout()
        self.theme_combo = QComboBox()
        for theme in THEME_OPTIONS:
            self.theme_combo.addItem(theme)
        self.theme_combo.setCurrentText(self.theme)
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        form.addRow("Theme", self.theme_combo)

        self.config_path_label = QLabel(self.config_path)
        self.config_path_label.setObjectName("MutedLabel")
        form.addRow("Config file", self.config_path_label)

        self.database_path_edit = QLineEdit(self.db.db_path)
        form.addRow("Database path", self.database_path_edit)
        form_layout.addLayout(form)

        button_row = QHBoxLayout()
        apply_db_button = QPushButton("Apply Database")
        apply_db_button.clicked.connect(self.apply_database_path)
        create_db_button = QPushButton("Create Database")
        create_db_button.setObjectName("SecondaryButton")
        create_db_button.clicked.connect(self.create_database_from_settings)
        reload_db_button = QPushButton("Reload Current")
        reload_db_button.setObjectName("SecondaryButton")
        reload_db_button.clicked.connect(self.reload_current_database)
        button_row.addWidget(apply_db_button)
        button_row.addWidget(create_db_button)
        button_row.addWidget(reload_db_button)
        button_row.addStretch()
        form_layout.addLayout(button_row)

        self.settings_message = QLabel("")
        self.settings_message.setObjectName("MutedLabel")
        form_layout.addWidget(self.settings_message)

        layout.addWidget(form_panel)
        layout.addStretch()
        return page

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def refresh_all(self) -> None:
        self.refresh_projects()
        self.refresh_project_table()
        self.refresh_tasks()

    def switch_page(self, index: int) -> None:
        index = max(0, min(index, self.page_stack.count() - 1))
        self.page_stack.setCurrentIndex(index)
        if index == 0:
            self.tasks_nav_button.setObjectName("NavButtonActive")
            self.projects_nav_button.setObjectName("NavButton")
            self.settings_nav_button.setObjectName("NavButton")
        elif index == 1:
            self.tasks_nav_button.setObjectName("NavButton")
            self.projects_nav_button.setObjectName("NavButtonActive")
            self.settings_nav_button.setObjectName("NavButton")
            self.refresh_project_table()
        else:
            self.tasks_nav_button.setObjectName("NavButton")
            self.projects_nav_button.setObjectName("NavButton")
            self.settings_nav_button.setObjectName("NavButtonActive")
        self.tasks_nav_button.style().unpolish(self.tasks_nav_button)
        self.tasks_nav_button.style().polish(self.tasks_nav_button)
        self.projects_nav_button.style().unpolish(self.projects_nav_button)
        self.projects_nav_button.style().polish(self.projects_nav_button)
        self.settings_nav_button.style().unpolish(self.settings_nav_button)
        self.settings_nav_button.style().polish(self.settings_nav_button)

    def refresh_projects(self) -> None:
        self.project_list.blockSignals(True)
        self.project_list.clear()

        all_item = QListWidgetItem("All Tasks")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self._apply_list_item_color(all_item)
        self.project_list.addItem(all_item)

        for project in self.db.get_projects():
            item = QListWidgetItem(project["name"])
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            self._apply_list_item_color(item)
            self.project_list.addItem(item)

        if self.project_list.currentRow() < 0:
            self.project_list.setCurrentRow(0)
        self.project_list.blockSignals(False)

        self.project_combo.clear()
        self.project_combo.addItem("None", None)
        for project in self.db.get_projects():
            self.project_combo.addItem(project["name"], project["id"])

    def refresh_project_table(self) -> None:
        if not hasattr(self, "projects_table"):
            return
        selected_id = self._selected_project_management_id()
        projects = self.db.get_project_summaries()
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
        self.project_count_label.setText(f"{len(projects)} project(s)")
        if selected_id is not None:
            self._select_project_management_row(selected_id)
        elif projects:
            self.projects_table.selectRow(0)
        self.update_project_buttons()

    def refresh_tasks(self) -> None:
        project_id = self._current_project_id()
        keyword = self.search_edit.text().strip()
        if keyword:
            tasks = self.db.search_tasks(keyword, limit=self.db.config.default_task_limit)
            if project_id is not None:
                tasks = [task for task in tasks if task.get("project_id") == project_id]
        else:
            tasks = self.db.get_tasks(project_id=project_id, limit=self.db.config.default_task_limit)

        self.tasks = tasks
        self.task_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                task.get("id"),
                task.get("title"),
                task.get("status_text"),
                task.get("priority_text"),
                task.get("project_name") or "",
                task.get("due_date") or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self._apply_plain_cell_color(item, row)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, task.get("id"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2:
                    status_colors = badge_colors_for_theme(self.theme, QApplication.instance())["status"]
                    self._apply_badge_color(item, status_colors.get(str(value), status_colors["not_started"]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    priority_colors = badge_colors_for_theme(self.theme, QApplication.instance())["priority"]
                    self._apply_badge_color(item, priority_colors.get(str(value), priority_colors["None"]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.task_table.setItem(row, column, item)

        self.task_table.resizeRowsToContents()
        self.task_count_label.setText(f"{len(tasks)} task(s)")
        self.task_stack.setCurrentWidget(self.task_table if tasks else self.empty_label)
        self.statusBar().showMessage(f"{len(tasks)} task(s)")
        if tasks:
            self.task_table.selectRow(0)
        else:
            self.selected_task_id = None
            self._clear_detail_panel()

    def load_selected_task(self) -> None:
        rows = self.task_table.selectionModel().selectedRows()
        if not rows:
            return
        task_id = self.task_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        task = self.db.get_task(int(task_id))
        if not task:
            return

        self.selected_task_id = int(task_id)
        self.title_edit.setText(task.get("title") or "")
        self.description_edit.setPlainText(task.get("description") or "")
        self.status_combo.setCurrentText(task.get("status_text") or STATUS_LABELS.get(task.get("status"), "not_started"))
        self.priority_combo.setCurrentIndex(int(task.get("priority") or 0))
        self._set_project_combo(task.get("project_id"))
        self.due_edit.setText(task.get("due_date") or "")

    def open_new_task_dialog(self) -> None:
        dialog = TaskDialog(self.db.get_projects(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.task_data()
        try:
            task_id = self.db.create_task(**data)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Task", str(exc))
            return

        self.refresh_all()
        self._select_task(task_id)

    def open_new_project_dialog(self) -> None:
        dialog = ProjectDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.project_name()
        try:
            project_id = self.db.create_project(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Project", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Project", f"Could not create project:\n{exc}")
            return
        self.refresh_all()
        self._select_project_management_row(project_id)

    def open_rename_project_dialog(self) -> None:
        project_id = self._selected_project_management_id()
        if project_id is None:
            QMessageBox.information(self, "Project", "Select a project first.")
            return
        project = self.db.get_project(project_id)
        if not project:
            QMessageBox.warning(self, "Project", "Project was not found.")
            self.refresh_all()
            return
        dialog = ProjectDialog(project["name"], parent=self)
        dialog.setWindowTitle("Rename Project")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            changed = self.db.update_project(project_id, name=dialog.project_name())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Project", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Project", f"Could not rename project:\n{exc}")
            return
        if not changed:
            QMessageBox.warning(self, "Project", "Project was not found.")
            return
        self.refresh_all()
        self._select_project_management_row(project_id)

    def delete_selected_project(self) -> None:
        project_id = self._selected_project_management_id()
        if project_id is None:
            QMessageBox.information(self, "Project", "Select a project first.")
            return
        project = self.db.get_project(project_id)
        if not project:
            QMessageBox.warning(self, "Project", "Project was not found.")
            self.refresh_all()
            return
        reply = QMessageBox.question(self, "Delete Project", f"Delete empty project '{project['name']}'?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.db.delete_project(project_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Delete Project", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Project", f"Could not delete project:\n{exc}")
            return
        if not deleted:
            QMessageBox.warning(self, "Project", "Project was not found.")
            return
        self.refresh_all()

    def save_selected_task(self) -> None:
        if self.selected_task_id is None:
            return

        due_date = self.due_edit.text().strip() or None
        try:
            normalize_due_date(due_date)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Due Date", str(exc))
            return

        changed = self.db.update_task(
            self.selected_task_id,
            title=self.title_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            status=STATUS_VALUES[self.status_combo.currentText()],
            priority=self.priority_combo.currentData(),
            project_id=self.project_combo.currentData(),
            due_date=due_date,
        )
        if not changed:
            QMessageBox.warning(self, "Save Failed", "Task was not found.")
            return

        self.refresh_all()
        self._select_task(self.selected_task_id)

    def complete_selected_task(self) -> None:
        if self.selected_task_id is None:
            return
        self.db.complete_task(self.selected_task_id)
        self.refresh_all()
        self._select_task(self.selected_task_id)

    def delete_selected_task(self) -> None:
        if self.selected_task_id is None:
            return
        reply = QMessageBox.question(self, "Delete Task", "Delete the selected task?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_task(self.selected_task_id)
        self.refresh_all()

    def undo_last_operation(self) -> None:
        history = self.db.undo_last_operation()
        if not history:
            QMessageBox.information(self, "Undo", "No operation to undo.")
            return
        self.refresh_all()

    def open_history_dialog(self) -> None:
        dialog = HistoryDialog(self.db, self.theme, parent=self)
        dialog.history_changed.connect(self.refresh_all)
        dialog.exec()

    def apply_theme(self, theme: str) -> None:
        self.theme = theme
        self._apply_theme_to_app(theme)
        self._refresh_action_icons()
        try:
            save_ui_theme(theme, self.config_path)
        except Exception as exc:
            QMessageBox.warning(self, "Theme", f"Could not save theme setting:\n{exc}")
        self.refresh_tasks()

    def _apply_theme_to_app(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setProperty("mindtask_theme", theme)
            app.setStyleSheet(build_app_style(theme, app))

    def apply_database_path(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            QMessageBox.warning(self, "Database", "Database path is required.")
            return

        try:
            tested_db = self._open_database_from_path(database_path)
            tested_db.get_tasks(limit=1)
        except Exception as exc:
            QMessageBox.warning(self, "Database", f"Could not open database:\n{exc}")
            return

        try:
            save_database_path(database_path, self.config_path)
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.settings_message.setText("Database updated.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Database", f"Database opened, but config update failed:\n{exc}")

    def create_database_from_settings(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            QMessageBox.warning(self, "Database", "Database path is required.")
            return

        target = Path(database_path)
        if target.exists():
            QMessageBox.warning(self, "Database", "Database file already exists. Choose a new path.")
            return

        reply = QMessageBox.question(
            self,
            "Create Database",
            "Create a new database at this path and switch to it?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            new_db = self._open_database_from_path(str(target))
            new_db.create_sample_data()
            new_db.get_tasks(limit=1)
            save_database_path(str(target), self.config_path)
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.settings_message.setText("Database created with sample data.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Database", f"Could not create database:\n{exc}")

    def reload_current_database(self) -> None:
        try:
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.settings_message.setText("Database reloaded.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Database", f"Could not reload database:\n{exc}")

    def _open_database_from_path(self, database_path: str) -> MindTaskDB:
        config = self.db.config
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".ini", delete=False) as fh:
            temp_config_path = fh.name
            fh.write("[database]\n")
            fh.write(f"path = {database_path}\n")
            fh.write(f"schema = {config.schema_path}\n\n")
            fh.write("[app]\n")
            fh.write(f"default_task_limit = {config.default_task_limit}\n")
            fh.write(f"default_search_limit = {config.default_search_limit}\n")
        try:
            return MindTaskDB(config_path=temp_config_path)
        finally:
            Path(temp_config_path).unlink(missing_ok=True)

    def _current_project_id(self) -> Optional[int]:
        item = self.project_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _clear_detail_panel(self) -> None:
        self.title_edit.clear()
        self.description_edit.clear()
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.project_combo.setCurrentIndex(0)
        self.due_edit.clear()

    def _set_project_combo(self, project_id: Optional[int]) -> None:
        for index in range(self.project_combo.count()):
            if self.project_combo.itemData(index) == project_id:
                self.project_combo.setCurrentIndex(index)
                return
        self.project_combo.setCurrentIndex(0)

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

    def _select_task(self, task_id: Optional[int]) -> None:
        if task_id is None:
            return
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == task_id:
                self.task_table.selectRow(row)
                return

    def _apply_badge_color(self, item: QTableWidgetItem, colors: tuple[str, str]) -> None:
        foreground, background = colors
        item.setForeground(QColor(foreground))
        item.setBackground(QColor(background))

    def _apply_plain_cell_color(self, item: QTableWidgetItem, row: int) -> None:
        colors = colors_for_theme(self.theme, QApplication.instance())
        item.setForeground(QColor(colors["text"]))
        item.setBackground(QColor(colors["input_bg"] if row % 2 == 0 else colors["panel_bg"]))

    def _apply_list_item_color(self, item: QListWidgetItem) -> None:
        colors = colors_for_theme(self.theme, QApplication.instance())
        item.setForeground(QColor(colors["text"]))
        item.setBackground(QColor(colors["input_bg"]))


class HistoryDialog(QDialog):
    """History viewer with scoped undo actions."""

    history_changed = Signal()

    def __init__(self, db: MindTaskDB, theme: str = THEME_SYSTEM, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.theme = theme
        self.setWindowTitle("History")
        self.resize(760, 460)
        self.setStyleSheet(build_app_style(theme, QApplication.instance()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel("Operation History")
        header.setObjectName("SectionLabel")
        layout.addWidget(header)

        self.history_table = QTableWidget(0, 6)
        self.history_table.setObjectName("TaskTable")
        self.history_table.setHorizontalHeaderLabels(["ID", "Created", "Action", "Entity", "State", "Undone"])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_table, 1)

        button_row = QHBoxLayout()
        self.undo_latest_button = QPushButton("Undo Latest")
        self.undo_latest_button.setObjectName("SecondaryButton")
        self.undo_latest_button.clicked.connect(self.undo_latest)
        self.undo_to_selected_button = QPushButton("Undo To Selected")
        self.undo_to_selected_button.setObjectName("DangerButton")
        self.undo_to_selected_button.clicked.connect(self.undo_to_selected)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(self.undo_latest_button)
        button_row.addWidget(self.undo_to_selected_button)
        button_row.addStretch()
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        rows = self.db.get_history(limit=100, include_undone=True)
        self.history_table.setRowCount(len(rows))
        for row_index, history in enumerate(rows):
            entity_id = f"#{history['entity_id']}" if history.get("entity_id") is not None else ""
            values = [
                history["id"],
                history["created_at"],
                history["action"],
                f"{history['entity_type']}{entity_id}",
                "undone" if history.get("undone_at") else "active",
                history.get("undone_at") or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                colors = colors_for_theme(self.theme, QApplication.instance())
                item.setForeground(QColor(colors["muted_text"] if history.get("undone_at") else colors["text"]))
                item.setBackground(QColor(colors["panel_bg"] if row_index % 2 else colors["input_bg"]))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, history["id"])
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 4:
                    history_colors = badge_colors_for_theme(self.theme, QApplication.instance())["history"]
                    badge = history_colors["undone" if history.get("undone_at") else "active"]
                    item.setForeground(QColor(badge[0]))
                    item.setBackground(QColor(badge[1]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(row_index, column, item)
        self.history_table.resizeRowsToContents()
        self.undo_latest_button.setEnabled(any(not row.get("undone_at") for row in rows))
        self.undo_to_selected_button.setEnabled(bool(rows))

    def undo_latest(self) -> None:
        history = self.db.undo_last_operation()
        if not history:
            QMessageBox.information(self, "Undo", "No operation to undo.")
            self.refresh()
            return
        self.history_changed.emit()
        self.refresh()

    def undo_to_selected(self) -> None:
        history_id = self._selected_history_id()
        if history_id is None:
            QMessageBox.information(self, "History", "Select a history record first.")
            return

        selected = self._selected_history_row()
        if selected is not None and selected.get("undone_at"):
            QMessageBox.information(self, "History", "Selected history record has already been undone.")
            return

        reply = QMessageBox.question(
            self,
            "Undo To Selected",
            "Undo all active operations from the latest down to the selected record?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        undone = self.db.undo_operations_until(history_id)
        if not undone:
            QMessageBox.information(self, "Undo", "No operation was undone.")
            self.refresh()
            return

        self.history_changed.emit()
        self.refresh()

    def _selected_history_id(self) -> Optional[int]:
        rows = self.history_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.history_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _selected_history_row(self) -> Optional[Dict[str, Any]]:
        history_id = self._selected_history_id()
        if history_id is None:
            return None
        for row in self.db.get_history(limit=100, include_undone=True):
            if row["id"] == history_id:
                return row
        return None


class ProjectDialog(QDialog):
    """Dialog for creating or renaming a project."""

    def __init__(self, name: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        theme = THEME_SYSTEM
        app = QApplication.instance()
        if app is not None:
            theme = app.property("mindtask_theme") or THEME_SYSTEM
        self.setStyleSheet(build_app_style(theme, app))

        self.name_edit = QLineEdit(name)

        form = QFormLayout(self)
        form.addRow(required_label("Name"), self.name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def project_name(self) -> str:
        return self.name_edit.text().strip()

    def _accept_if_valid(self) -> None:
        if not self.project_name():
            QMessageBox.warning(self, "Invalid Project", "Name is required.")
            return
        self.accept()


class TaskDialog(QDialog):
    """Dialog for creating a task."""

    def __init__(self, projects: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("New Task")
        theme = THEME_SYSTEM
        app = QApplication.instance()
        if app is not None:
            theme = app.property("mindtask_theme") or THEME_SYSTEM
        self.setStyleSheet(build_app_style(theme, app))

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.priority_combo = QComboBox()
        self.project_combo = QComboBox()
        self.due_edit = QLineEdit()
        self.due_edit.setPlaceholderText("YYYY-MM-DD HH:MM:SS")

        for priority, label in PRIORITY_LABELS.items():
            self.priority_combo.addItem(label, priority)
        self.priority_combo.setCurrentIndex(0)

        self.project_combo.addItem("None", None)
        for project in projects:
            self.project_combo.addItem(project["name"], project["id"])

        form = QFormLayout(self)
        form.addRow(required_label("Title"), self.title_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Priority", self.priority_combo)
        form.addRow("Project", self.project_combo)
        form.addRow("Due", self.due_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def task_data(self) -> Dict[str, Any]:
        due_date = self.due_edit.text().strip() or None
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "priority": self.priority_combo.currentData(),
            "project_id": self.project_combo.currentData(),
            "due_date": due_date,
        }

    def _accept_if_valid(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Invalid Task", "Title is required.")
            return
        try:
            normalize_due_date(self.due_edit.text().strip() or None)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Due Date", str(exc))
            return
        self.accept()
