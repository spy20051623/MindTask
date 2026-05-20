"""Task list page and task table behavior for the desktop window."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import cmp_to_key
from math import ceil
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QAction, QColor
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
from .style import THEME_DARK, badge_colors_for_theme, colors_for_theme, resolve_theme


SIDEBAR_WIDTH = 220
TASK_VIEW_TODAY = "__today__"
TASK_VIEW_TOMORROW = "__tomorrow__"
TASK_VIEW_THREE_DAYS = "__three_days__"
TASK_VIEW_SEVEN_DAYS = "__seven_days__"


class TaskPageMixin:
    """Mixin for the task list, project filter sidebar, and task shortcuts."""

    def _build_tasks_page(self) -> QWidget:
        self.tasks_page_container = QWidget()
        page_layout = QVBoxLayout(self.tasks_page_container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        self.tasks_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tasks_splitter.setHandleWidth(0)
        self.tasks_splitter.setChildrenCollapsible(False)
        self.tasks_splitter.setCursor(Qt.CursorShape.ArrowCursor)
        self.tasks_splitter.addWidget(self._build_sidebar())
        self.tasks_splitter.addWidget(self._build_task_table())
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.setMaximumWidth(0)
        self.detail_panel.hide()
        self.tasks_splitter.addWidget(self.detail_panel)
        self.tasks_splitter.setSizes([SIDEBAR_WIDTH, 960, 0])
        self._disable_task_splitter_handles()
        page_layout.addWidget(self.tasks_splitter)

        self.projects_drawer = self._build_project_drawer()
        self.projects_drawer.setParent(self.tasks_page_container)
        self.projects_drawer.hide()
        self.history_drawer = self._build_history_drawer()
        self.history_drawer.setParent(self.tasks_page_container)
        self.history_drawer.hide()
        return self.tasks_page_container

    def _disable_task_splitter_handles(self) -> None:
        for index in range(1, self.tasks_splitter.count()):
            handle = self.tasks_splitter.handle(index)
            handle.setEnabled(False)
            handle.setCursor(Qt.CursorShape.ArrowCursor)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.sidebar_views_label = self._section_label("")
        layout.addWidget(self.sidebar_views_label)
        self.task_view_list = QListWidget()
        self.task_view_list.setObjectName("DueFilterList")
        self.task_view_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.task_view_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.task_view_list.currentItemChanged.connect(self.handle_task_view_changed)
        layout.addWidget(self.task_view_list)

        self.sidebar_projects_label = self._section_label("")
        layout.addWidget(self.sidebar_projects_label)
        self.manage_projects_button = self._icon_button("", "fa6s.sliders", "Mgr", self.toggle_projects_drawer)
        self.manage_projects_button.setFixedSize(30, 30)
        self.manage_projects_button.setParent(panel)
        self.manage_projects_button.raise_()
        self.project_list = QListWidget()
        self.project_list.setObjectName("ProjectList")
        self.project_list.currentItemChanged.connect(self.handle_project_filter_changed)
        layout.addWidget(self.project_list)

        return panel

    def position_sidebar_action_button(self) -> None:
        if not hasattr(self, "manage_projects_button"):
            return
        parent = self.manage_projects_button.parentWidget()
        if parent is None:
            return
        margin = 8
        target_right = self.project_list.geometry().right() if hasattr(self, "project_list") else parent.contentsRect().right()
        x = target_right - self.manage_projects_button.width() + 1
        y = self.sidebar_projects_label.y() + (self.sidebar_projects_label.height() - self.manage_projects_button.height()) // 2
        self.manage_projects_button.move(
            max(margin, x),
            max(margin, y),
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

    def handle_task_view_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        current_value = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        current_value = current_value if isinstance(current_value, str) else None
        if self._handle_filter_change_cancelled(self.task_view_list, self._accepted_task_view, self._select_task_view):
            return
        self._accepted_task_view = current_value
        self.refresh_tasks(force_detail=True)

    def handle_project_filter_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        current_value = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        current_value = current_value if isinstance(current_value, int) else None
        if self._handle_filter_change_cancelled(self.project_list, self._accepted_project_filter, self._select_sidebar_project):
            return
        self._accepted_project_filter = current_value
        self.refresh_tasks(force_detail=True)

    def _handle_filter_change_cancelled(
        self,
        list_widget: QListWidget,
        accepted_value: object,
        restore: Callable[[object], None],
    ) -> bool:
        if getattr(self, "_restoring_filter_selection", False):
            return True
        if self.confirm_task_detail_transition():
            return False
        self._restore_filter_selection(list_widget, accepted_value, restore)
        QTimer.singleShot(0, lambda: self._restore_filter_selection(list_widget, accepted_value, restore))
        return True

    def _restore_filter_selection(
        self,
        list_widget: QListWidget,
        accepted_value: object,
        restore: Callable[[object], None],
    ) -> None:
        self._restoring_filter_selection = True
        was_blocked = list_widget.signalsBlocked()
        try:
            list_widget.blockSignals(True)
            restore(accepted_value)
        finally:
            list_widget.blockSignals(was_blocked)
            self._restoring_filter_selection = False

    def clear_search(self) -> None:
        if not self.search_edit.text() and not self.active_search_keyword:
            return
        if not self.confirm_task_detail_transition():
            return
        self.search_edit.clear()
        self.refresh_tasks(force_detail=True)

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
        focus_widget = QApplication.focusWidget()
        if focus_widget is not None and focus_widget.__class__.__name__ == "ChecklistItemEdit":
            self.refresh_checklist_from_description()
            return
        if self._is_history_drawer_open():
            self.close_history_drawer()
            return
        if self._is_projects_drawer_open():
            self.close_projects_drawer()
            return
        if self._is_task_detail_open() and self._is_description_editing():
            self._show_description_preview()
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
        if self._is_tasks_page() and self._is_task_detail_open() and not self._selected_task_completed():
            self.complete_selected_task()

    def shortcut_delete_task(self) -> None:
        if self._is_tasks_page() and self._is_task_detail_open():
            self.delete_selected_task()

    def _is_tasks_page(self) -> bool:
        return self.page_stack.currentIndex() == 0

    def _is_task_detail_open(self) -> bool:
        return (
            hasattr(self, "detail_panel")
            and (self.selected_task_id is not None or getattr(self, "detail_mode", "closed") == "create")
            and not self.detail_panel.isHidden()
            and (
                self.detail_panel.maximumWidth() > 0
                or self.detail_panel.width() > 0
                or getattr(self, "detail_animation_opens", False)
            )
        )

    def _is_projects_drawer_open(self) -> bool:
        return (
            hasattr(self, "projects_drawer")
            and not self.projects_drawer.isHidden()
            and self.projects_drawer.width() > 0
        )

    def _is_history_drawer_open(self) -> bool:
        return (
            hasattr(self, "history_drawer")
            and not self.history_drawer.isHidden()
            and self.history_drawer.width() > 0
        )

    def refresh_projects(self) -> None:
        selected_view = self._current_task_view() or None
        selected_sidebar_project_id = self._current_project_id()
        selected_detail_project_id = self.project_combo.currentData() if hasattr(self, "project_combo") else None

        self.task_view_list.blockSignals(True)
        self.task_view_list.clear()

        all_item = QListWidgetItem(self.tr("all"))
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        all_item.setSizeHint(QSize(0, 28))
        self._apply_list_item_color(all_item)
        self.task_view_list.addItem(all_item)

        due_filter_items = [
            ("due_today", TASK_VIEW_TODAY),
            ("due_tomorrow", TASK_VIEW_TOMORROW),
            ("due_three_days", TASK_VIEW_THREE_DAYS),
            ("due_seven_days", TASK_VIEW_SEVEN_DAYS),
        ]
        for label_key, value in due_filter_items:
            item = QListWidgetItem(self.tr(label_key))
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setSizeHint(QSize(0, 28))
            self._apply_list_item_color(item)
            self.task_view_list.addItem(item)

        self._select_task_view(selected_view)
        if self.task_view_list.currentRow() < 0:
            self.task_view_list.setCurrentRow(0)
        self._fit_task_view_list_height()
        self.task_view_list.blockSignals(False)

        self.project_list.blockSignals(True)
        self.project_list.clear()

        all_projects_item = QListWidgetItem(self.tr("all"))
        all_projects_item.setData(Qt.ItemDataRole.UserRole, None)
        self._apply_list_item_color(all_projects_item)
        self.project_list.addItem(all_projects_item)

        for project in self.db.get_projects():
            item = QListWidgetItem(project["name"])
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            self._apply_list_item_color(item)
            self.project_list.addItem(item)

        self._select_sidebar_project(selected_sidebar_project_id)
        if self.project_list.currentRow() < 0:
            self.project_list.setCurrentRow(0)
        self.project_list.blockSignals(False)
        self._accepted_task_view = self._current_task_view()
        self._accepted_project_filter = self._current_project_id()

        self.project_combo.clear()
        self.project_combo.addItem(self.tr("none"), None)
        for project in self.db.get_projects():
            self.project_combo.addItem(project["name"], project["id"])
        self._set_project_combo(selected_detail_project_id)

    def refresh_tasks(self, force_detail: bool = False) -> bool:
        if not self.confirm_task_detail_transition(force=force_detail):
            return False
        project_id = self._current_project_id()
        task_view = self._current_task_view()
        keyword = self.search_edit.text().strip()
        self.active_search_keyword = keyword
        self.update_search_clear_action()
        if keyword:
            tasks = self.db.search_tasks(keyword, limit=self.db.config.default_task_limit)
            if project_id is not None:
                tasks = [task for task in tasks if task.get("project_id") == project_id]
        else:
            tasks = self.db.get_tasks(project_id=project_id, limit=self.db.config.default_task_limit)

        if task_view is not None:
            tasks = self._filter_due_tasks(tasks, task_view)

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
            is_overdue = self._is_task_overdue(task)
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
                if is_overdue and column == 5:
                    self._apply_overdue_cell_color(item)
                self.task_table.setItem(row, column, item)

        self.task_table.resizeRowsToContents()
        self.task_count_label.setText(self.tr("task_count", count=len(tasks)))
        self.task_stack.setCurrentWidget(self.task_table if tasks else self.empty_label)
        self.statusBar().showMessage(self.tr("task_count", count=len(tasks)))
        selected_task = None
        if self.selected_task_id is not None:
            selected_task = next((task for task in tasks if task["id"] == self.selected_task_id), None)
        if selected_task is not None:
            self._select_task(self.selected_task_id)
            self._populate_task_detail(selected_task)
        else:
            self.selected_task_id = None
            self._clear_task_selection()
            self._clear_detail_panel()
            self.close_task_detail(clear_selection=False, force=True)
        return True

    def sort_tasks_by_column(self, column: int) -> None:
        if not self.confirm_task_detail_transition():
            return
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
        self.refresh_tasks(force_detail=True)

    def _update_task_sort_indicator(self) -> None:
        if hasattr(self, "task_table"):
            self.task_table.horizontalHeader().setSortIndicator(self.task_sort_column, self.task_sort_order)

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

    def load_selected_task(self) -> None:
        if getattr(self, "_restoring_task_selection", False):
            return
        rows = self.task_table.selectionModel().selectedRows()
        if not rows:
            return
        task_id = self.task_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        task_id = int(task_id)
        if self.selected_task_id == task_id and self._is_task_detail_open():
            return
        if self._is_task_detail_open():
            if not self.confirm_task_detail_transition():
                self._restore_task_selection(self.selected_task_id)
                return
        task = self.db.get_task(task_id)
        if not task:
            return

        self.selected_task_id = task_id
        self._populate_task_detail(task)
        self.open_task_detail()

    def _populate_task_detail(self, task: Dict[str, Any]) -> None:
        self.detail_mode = "edit"
        self._set_create_detail_mode(False)
        self.task_detail_title_label.setText(self.tr("task_detail_with_id", id=self.selected_task_id))
        self.title_edit.setText(task.get("title") or "")
        self.description_edit.setPlainText(task.get("description") or "")
        self._show_description_preview()
        self._set_status_combo(int(task.get("status") or 0))
        self._set_priority_combo(int(task.get("priority") or 0))
        self._set_project_combo(task.get("project_id"))
        self.due_editor.set_due_value(task.get("due_date"), task.get("due_mode"))
        self._set_task_detail_metadata(task)
        self._set_detail_original_values(task)
        self.refresh_task_detail_history()

    def discard_selected_task_changes(self) -> None:
        if self.selected_task_id is None and getattr(self, "detail_mode", "closed") != "create":
            return
        self.close_task_detail(force=True)

    def _current_project_id(self) -> Optional[int]:
        value = self._current_project_value()
        return value if isinstance(value, int) else None

    def _current_task_view(self) -> Optional[str]:
        item = self.task_view_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def _current_project_value(self) -> object:
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

    def _set_task_detail_metadata(self, task: Dict[str, Any]) -> None:
        due_alert = self._task_due_alert(task)
        if due_alert is None:
            self.due_alert_row.hide()
            self.due_alert_spacer_label.hide()
            self.due_alert_value_label.clear()
        else:
            severity, message = due_alert
            self.due_alert_value_label.setText(message)
            self._apply_due_alert_style(severity)
            self.due_alert_spacer_label.show()
            self.due_alert_row.show()
        self.created_at_value_label.setText(self._format_detail_timestamp(task.get("created_at")))
        self.updated_at_value_label.setText(self._format_detail_timestamp(task.get("updated_at")))
        self.completed_at_value_label.setText(self._format_detail_timestamp(task.get("completed_at")) or self.tr("not_completed"))
        self.complete_button.setVisible(task.get("status") != 3)

    def refresh_current_task_detail_text(self) -> None:
        if self.selected_task_id is None or not self._is_task_detail_open():
            return
        task = self.db.get_task(self.selected_task_id)
        if not task:
            return
        self.task_detail_title_label.setText(self.tr("task_detail_with_id", id=self.selected_task_id))
        self._set_task_detail_metadata(task)
        self.refresh_task_detail_history()

    def _selected_task_completed(self) -> bool:
        if self.selected_task_id is None:
            return False
        task = self.db.get_task(self.selected_task_id)
        return bool(task and task.get("status") == 3)

    def _task_due_alert(self, task: Dict[str, Any]) -> Optional[tuple[str, str]]:
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
                return "danger", self.tr("due_alert_overdue")
            if days == 0:
                return "danger", self.tr("due_alert_today")
            if days <= 3:
                return "warning", self.tr("due_alert_days_left", days=days)
            return None
        try:
            task_due_at = datetime.strptime(str(due_date), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        remaining = task_due_at - datetime.now()
        if remaining.total_seconds() < 0:
            return "danger", self.tr("due_alert_overdue")
        if remaining < timedelta(hours=24):
            total_minutes = max(1, ceil(remaining.total_seconds() / 60))
            hours, minutes = divmod(total_minutes, 60)
            return "danger", self.tr("due_alert_time_left", hours=hours, minutes=minutes)
        task_due_date = self._task_due_date(task)
        if task_due_date is None:
            return None
        days = (task_due_date - date.today()).days
        if 1 <= days <= 3:
            return "warning", self.tr("due_alert_days_left", days=days)
        return None

    def _apply_due_alert_style(self, severity: str) -> None:
        if severity == "danger":
            foreground = "#ef4444" if resolve_theme(self.theme, QApplication.instance()) != THEME_DARK else "#f87171"
        else:
            foreground = "#f59e0b" if resolve_theme(self.theme, QApplication.instance()) != THEME_DARK else "#fbbf24"
        icon_style = (
            f"color: {foreground}; border: 1px solid {foreground}; border-radius: 9px; "
            "font-weight: 700; background: transparent;"
        )
        text_style = f"color: {foreground}; font-weight: 600; background: transparent;"
        self.due_alert_icon_label.setStyleSheet(icon_style)
        self.due_alert_value_label.setStyleSheet(text_style)

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

    def _select_task_view(self, value: object) -> None:
        for row in range(self.task_view_list.count()):
            item = self.task_view_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == value:
                self.task_view_list.setCurrentRow(row)
                return

    def _fit_task_view_list_height(self) -> None:
        row_count = self.task_view_list.count()
        if row_count <= 0:
            return
        row_height = 28
        frame_height = self.task_view_list.frameWidth() * 2
        viewport_padding = 0
        self.task_view_list.setFixedHeight(row_height * row_count + frame_height + viewport_padding)

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

    def _restore_task_selection(self, task_id: Optional[int]) -> None:
        self._restoring_task_selection = True
        try:
            if task_id is None:
                self._clear_task_selection()
            else:
                self._select_task(task_id)
        finally:
            self._restoring_task_selection = False
