"""Task list page and task table behavior for the desktop window."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .constants import PRIORITY_LABELS, PRIORITY_TRANSLATION_KEYS, STATUS_LABELS, STATUS_TRANSLATION_KEYS
from .icons import themed_icon
from .style import badge_colors_for_theme


DETAIL_PANEL_WIDTH = 480
SIDEBAR_WIDTH = 220


class TaskPageMixin:
    """Mixin for the task list, project filter sidebar, and task shortcuts."""

    def _build_tasks_page(self) -> QWidget:
        self.tasks_page_container = QWidget()
        page_layout = QVBoxLayout(self.tasks_page_container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        self.tasks_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tasks_splitter.addWidget(self._build_sidebar())
        self.tasks_splitter.addWidget(self._build_task_table())
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.setMaximumWidth(0)
        self.detail_panel.hide()
        self.tasks_splitter.addWidget(self.detail_panel)
        self.tasks_splitter.setSizes([SIDEBAR_WIDTH, 960, 0])
        self.tasks_splitter.splitterMoved.connect(lambda _pos, _index: self.position_sidebar_action_button())
        page_layout.addWidget(self.tasks_splitter)

        self.projects_drawer = self._build_project_drawer()
        self.projects_drawer.setParent(self.tasks_page_container)
        self.projects_drawer.hide()
        return self.tasks_page_container

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.sidebar_projects_label = self._section_label("")
        layout.addWidget(self.sidebar_projects_label)
        self.manage_projects_button = self._icon_button("", "fa6s.sliders", "Mgr", self.toggle_projects_drawer)
        self.manage_projects_button.setFixedSize(30, 30)
        self.manage_projects_button.setParent(panel)
        self.manage_projects_button.raise_()
        self.project_list = QListWidget()
        self.project_list.setObjectName("ProjectList")
        self.project_list.currentItemChanged.connect(lambda _current, _previous: self.refresh_tasks())
        layout.addWidget(self.project_list)

        return panel

    def position_sidebar_action_button(self) -> None:
        if not hasattr(self, "manage_projects_button"):
            return
        parent = self.manage_projects_button.parentWidget()
        if parent is None:
            return
        margin = 8
        x = parent.contentsRect().right() - margin - self.manage_projects_button.width() + 1
        self.manage_projects_button.move(
            max(margin, x),
            8,
        )
        self.manage_projects_button.raise_()

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
        self.clear_search_action = QAction(self)
        self.clear_search_action.setIcon(themed_icon("fa6s.xmark", self.theme))
        self.clear_search_action.triggered.connect(self.clear_search)
        self.search_edit.addAction(self.clear_search_action, QLineEdit.ActionPosition.TrailingPosition)
        self.search_edit.textChanged.connect(self.update_search_clear_action)
        self.search_edit.returnPressed.connect(self.refresh_tasks)
        self.update_search_clear_action()
        actions_row.addWidget(self.search_edit, 1)

        self.add_button = self._icon_button(
            "",
            "fa6s.plus",
            "New",
            self.open_new_task_dialog,
        )
        actions_row.addWidget(self.add_button)

        self.refresh_button = self._icon_button(
            "",
            "fa6s.arrows-rotate",
            "Ref",
            self.refresh_all,
        )
        actions_row.addWidget(self.refresh_button)

        self.history_button = self._icon_button(
            "",
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
        self.tasks_title_label = self._section_label("")
        header_row.addWidget(self.tasks_title_label)
        self.task_count_label = QLabel()
        self.task_count_label.setObjectName("MutedLabel")
        header_row.addStretch()
        header_row.addWidget(self.task_count_label)
        layout.addWidget(header)

        self.task_table = QTableWidget(0, 6)
        self.task_table.setObjectName("TaskTable")
        self.task_table.setHorizontalHeaderLabels(["ID", "", "", "", "", ""])
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
        self.task_table.horizontalHeader().setSectionsClickable(True)
        self.task_table.horizontalHeader().setSortIndicatorShown(True)
        self.task_table.horizontalHeader().sectionClicked.connect(self.sort_tasks_by_column)
        self.task_table.itemSelectionChanged.connect(self.load_selected_task)
        self.task_table.cellClicked.connect(lambda _row, _column: self.load_selected_task())

        self.empty_label = QLabel()
        self.empty_label.setObjectName("EmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.task_stack = QStackedWidget()
        self.task_stack.addWidget(self.task_table)
        self.task_stack.addWidget(self.empty_label)
        layout.addWidget(self.task_stack, 1)

        return panel

    def set_task_table_compact_mode(self, compact: bool) -> None:
        if not hasattr(self, "task_table"):
            return
        for column in (2, 3, 4, 5):
            self.task_table.setColumnHidden(column, compact)

    def update_search_clear_action(self) -> None:
        self.clear_search_action.setVisible(bool(self.search_edit.text()) or bool(self.active_search_keyword))

    def clear_search(self) -> None:
        if not self.search_edit.text() and not self.active_search_keyword:
            return
        self.search_edit.clear()
        self.refresh_tasks()

    def shortcut_new_task(self) -> None:
        if self._is_tasks_page():
            self.open_new_task_dialog()

    def shortcut_focus_search(self) -> None:
        if not self._is_tasks_page():
            return
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def shortcut_escape_tasks(self) -> None:
        if not self._is_tasks_page():
            return
        if self._is_projects_drawer_open():
            self.close_projects_drawer()
            return
        if self._is_task_detail_open():
            self.close_task_detail()
            return
        self.clear_search()

    def shortcut_open_projects(self) -> None:
        if self._is_tasks_page():
            self.toggle_projects_drawer()

    def toggle_projects_drawer(self) -> None:
        if self._is_projects_drawer_open():
            self.close_projects_drawer()
        else:
            self.open_projects_drawer()

    def shortcut_save_task(self) -> None:
        if self._is_tasks_page() and self._is_task_detail_open():
            self.save_selected_task()

    def shortcut_complete_task(self) -> None:
        if self._is_tasks_page() and self._is_task_detail_open():
            self.complete_selected_task()

    def shortcut_delete_task(self) -> None:
        if self._is_tasks_page() and self._is_task_detail_open():
            self.delete_selected_task()

    def _is_tasks_page(self) -> bool:
        return self.page_stack.currentIndex() == 0

    def _is_task_detail_open(self) -> bool:
        return (
            hasattr(self, "detail_panel")
            and self.selected_task_id is not None
            and not self.detail_panel.isHidden()
            and self.detail_panel.maximumWidth() > 0
        )

    def _is_projects_drawer_open(self) -> bool:
        return (
            hasattr(self, "projects_drawer")
            and not self.projects_drawer.isHidden()
            and self.projects_drawer.width() > 0
        )

    def refresh_projects(self) -> None:
        selected_sidebar_project_id = self._current_project_id()
        selected_detail_project_id = self.project_combo.currentData() if hasattr(self, "project_combo") else None
        self.project_list.blockSignals(True)
        self.project_list.clear()

        all_item = QListWidgetItem(self.tr("all_tasks"))
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self._apply_list_item_color(all_item)
        self.project_list.addItem(all_item)

        for project in self.db.get_projects():
            item = QListWidgetItem(project["name"])
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            self._apply_list_item_color(item)
            self.project_list.addItem(item)

        self._select_sidebar_project(selected_sidebar_project_id)
        if self.project_list.currentRow() < 0:
            self.project_list.setCurrentRow(0)
        self.project_list.blockSignals(False)

        self.project_combo.clear()
        self.project_combo.addItem(self.tr("none"), None)
        for project in self.db.get_projects():
            self.project_combo.addItem(project["name"], project["id"])
        self._set_project_combo(selected_detail_project_id)

    def refresh_tasks(self) -> None:
        project_id = self._current_project_id()
        keyword = self.search_edit.text().strip()
        self.active_search_keyword = keyword
        self.update_search_clear_action()
        if keyword:
            tasks = self.db.search_tasks(keyword, limit=self.db.config.default_task_limit)
            if project_id is not None:
                tasks = [task for task in tasks if task.get("project_id") == project_id]
        else:
            tasks = self.db.get_tasks(project_id=project_id, limit=self.db.config.default_task_limit)

        tasks = self._sort_tasks(tasks)
        self.tasks = tasks
        self.task_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                task.get("id"),
                task.get("title"),
                self.tr(STATUS_TRANSLATION_KEYS.get(task.get("status"), "status_not_started")),
                self.tr(PRIORITY_TRANSLATION_KEYS.get(task.get("priority"), "priority_none")),
                task.get("project_name") or "",
                self._format_task_due(task),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self._apply_plain_cell_color(item, row)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, task.get("id"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2:
                    status_colors = badge_colors_for_theme(self.theme, QApplication.instance())["status"]
                    status_key = task.get("status_text") or STATUS_LABELS.get(task.get("status"), "not_started")
                    self._apply_badge_color(item, status_colors.get(str(status_key), status_colors["not_started"]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    priority_colors = badge_colors_for_theme(self.theme, QApplication.instance())["priority"]
                    priority_key = task.get("priority_text") or PRIORITY_LABELS.get(task.get("priority"), "None")
                    self._apply_badge_color(item, priority_colors.get(str(priority_key), priority_colors["None"]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.task_table.setItem(row, column, item)

        self.task_table.resizeRowsToContents()
        self.task_count_label.setText(self.tr("task_count", count=len(tasks)))
        self.task_stack.setCurrentWidget(self.task_table if tasks else self.empty_label)
        self.statusBar().showMessage(self.tr("task_count", count=len(tasks)))
        if self.selected_task_id is not None and any(task["id"] == self.selected_task_id for task in tasks):
            self._select_task(self.selected_task_id)
        else:
            self.selected_task_id = None
            self._clear_task_selection()
            self._clear_detail_panel()
            self.close_task_detail(clear_selection=False)

    def sort_tasks_by_column(self, column: int) -> None:
        if column == self.task_sort_column:
            self.task_sort_order = (
                Qt.SortOrder.DescendingOrder
                if self.task_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self.task_sort_column = column
            self.task_sort_order = Qt.SortOrder.AscendingOrder
        self._update_task_sort_indicator()
        self.refresh_tasks()

    def _update_task_sort_indicator(self) -> None:
        if hasattr(self, "task_table"):
            self.task_table.horizontalHeader().setSortIndicator(self.task_sort_column, self.task_sort_order)

    def _sort_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        reverse = self.task_sort_order == Qt.SortOrder.DescendingOrder

        def value_for(task: Dict[str, Any]) -> Any:
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

        present = [task for task in tasks if value_for(task) not in {None, ""}]
        missing = [task for task in tasks if value_for(task) in {None, ""}]
        return sorted(present, key=value_for, reverse=reverse) + sorted(missing, key=lambda task: task.get("id") or 0)

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
        self._set_status_combo(int(task.get("status") or 0))
        self._set_priority_combo(int(task.get("priority") or 0))
        self._set_project_combo(task.get("project_id"))
        self.due_editor.set_due_value(task.get("due_date"), task.get("due_mode"))
        self.open_task_detail()

    def _current_project_id(self) -> Optional[int]:
        item = self.project_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _clear_task_selection(self) -> None:
        selection_model = self.task_table.selectionModel()
        if selection_model is not None:
            selection_model.clearSelection()
            selection_model.clearCurrentIndex()

    def _format_task_due(self, task: Dict[str, Any]) -> str:
        due_date = task.get("due_date")
        if not due_date:
            return ""
        if task.get("due_mode") == "all_day":
            return f"{str(due_date)[:10]} {self.tr('all_day')}"
        return str(due_date)
        self.task_table.clearSelection()

    def _select_sidebar_project(self, project_id: Optional[int]) -> None:
        for row in range(self.project_list.count()):
            item = self.project_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                self.project_list.setCurrentRow(row)
                return

    def _select_task(self, task_id: Optional[int]) -> None:
        if task_id is None:
            return
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == task_id:
                self.task_table.selectRow(row)
                return
