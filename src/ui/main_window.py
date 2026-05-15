"""Main desktop window for MindTask."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import (
    MindTaskDB,
    get_config_path,
    normalize_due_date,
)
from .constants import (
    PRIORITY_LABELS,
    PRIORITY_TRANSLATION_KEYS,
    STATUS_LABELS,
    STATUS_TRANSLATION_KEYS,
    STATUS_VALUES,
)
from .dialog_helpers import confirm_question, required_label
from .dialogs import HistoryDialog, TaskDialog
from .due_date_editor import DueDateEditor
from .icons import icon_button, set_action_button_icon, themed_icon
from .i18n import Translator
from .project_page import ProjectPageMixin
from .settings_page import SettingsPageMixin
from .style import build_app_style, colors_for_theme
from .task_page import TaskPageMixin
from .shortcut_editor import SHIFTED_KEY_ALIASES


DETAIL_PANEL_MIN_WIDTH = 420
DETAIL_PANEL_WIDTH = 480
SIDEBAR_WIDTH = 220


class MindTaskWindow(SettingsPageMixin, ProjectPageMixin, TaskPageMixin, QMainWindow):
    """Task-focused desktop shell around the existing MindTask core."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = str(get_config_path(config_path))
        self.db = MindTaskDB(config_path=config_path)
        self.tasks: List[Dict[str, Any]] = []
        self.selected_task_id: Optional[int] = None
        self.theme = self.db.config.ui_theme
        self.language = self.db.config.ui_language
        self.due_day_end = self.db.config.ui_due_day_end
        self.shortcut_sequences = dict(self.db.config.ui_shortcuts)
        self.task_sort_column = 0
        self.task_sort_order = Qt.SortOrder.AscendingOrder
        self.project_sort_column = 0
        self.project_sort_order = Qt.SortOrder.AscendingOrder
        self.active_search_keyword = ""
        self.translator = Translator(self.language)
        self._apply_theme_to_app(self.theme)

        self.setWindowTitle("MindTask")
        self.resize(1180, 720)

        self._build_layout()
        self._build_shortcuts()
        self.retranslate_ui()
        self.refresh_all()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

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

    def _build_shortcuts(self) -> None:
        handlers = {
            "open_tasks": lambda: self.switch_page(0),
            "open_projects": lambda: self.switch_page(1),
            "open_settings": lambda: self.switch_page(2),
            "new_task": self.shortcut_new_task,
            "focus_search": self.shortcut_focus_search,
            "escape_tasks": self.shortcut_escape_tasks,
            "refresh": self.refresh_all,
            "undo": self.undo_last_operation,
            "history": self.open_history_dialog,
            "save_task": self.shortcut_save_task,
            "complete_task": self.shortcut_complete_task,
            "delete_task": self.shortcut_delete_task,
        }
        if hasattr(self, "shortcuts"):
            for shortcut in self.shortcuts:
                shortcut.setEnabled(False)
                shortcut.deleteLater()
        self.shortcuts: List[QShortcut] = []
        for action, handler in handlers.items():
            sequence = self.shortcut_sequences.get(action, "")
            for key_sequence in self._shortcut_key_sequences(sequence):
                shortcut = QShortcut(key_sequence, self)
                shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
                shortcut.activated.connect(handler)
                self.shortcuts.append(shortcut)
        if getattr(self, "shortcut_active_rows", set()):
            for shortcut in self.shortcuts:
                shortcut.setEnabled(False)

    def _shortcut_key_sequences(self, sequence: str) -> List[QKeySequence]:
        key_sequence = QKeySequence(sequence)
        if key_sequence.isEmpty():
            return []

        sequences = [key_sequence]
        portable_text = key_sequence.toString(QKeySequence.SequenceFormat.PortableText)
        alias = self._enter_shortcut_alias(portable_text)
        if alias:
            sequences.append(QKeySequence(alias))
        shifted_alias = self._shifted_shortcut_alias(portable_text)
        if shifted_alias:
            sequences.append(QKeySequence(shifted_alias))
        return sequences

    def _enter_shortcut_alias(self, portable_text: str) -> str:
        parts = portable_text.split("+")
        if not parts:
            return ""
        if parts[-1] == "Enter":
            return "+".join([*parts[:-1], "Return"])
        if parts[-1] == "Return":
            return "+".join([*parts[:-1], "Enter"])
        return ""

    def _shifted_shortcut_alias(self, portable_text: str) -> str:
        parts = portable_text.split("+")
        if "Shift" not in parts[:-1]:
            return ""
        key_text = parts[-1]
        for shifted_key, base_key in SHIFTED_KEY_ALIASES.items():
            base_text = QKeySequence(base_key).toString(QKeySequence.SequenceFormat.PortableText)
            if key_text == base_text:
                shifted_text = QKeySequence(shifted_key).toString(QKeySequence.SequenceFormat.PortableText)
                return "+".join([*parts[:-1], shifted_text])
        return ""

    def _build_bottom_navigation(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("BottomNav")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.tasks_nav_button = QPushButton()
        self.tasks_nav_button.setObjectName("NavButtonActive")
        self.tasks_nav_button.clicked.connect(lambda: self.switch_page(0))
        self.projects_nav_button = QPushButton()
        self.projects_nav_button.setObjectName("NavButton")
        self.projects_nav_button.clicked.connect(lambda: self.switch_page(1))
        self.settings_nav_button = QPushButton()
        self.settings_nav_button.setObjectName("NavButton")
        self.settings_nav_button.clicked.connect(lambda: self.switch_page(2))

        layout.addStretch()
        layout.addWidget(self.tasks_nav_button)
        layout.addWidget(self.projects_nav_button)
        layout.addWidget(self.settings_nav_button)
        layout.addStretch()
        return panel

    def _icon_button(self, tooltip: str, icon_name: str, fallback_text: str, handler: Any) -> QPushButton:
        return icon_button(tooltip, icon_name, fallback_text, self.theme, handler)

    def _set_action_button_icon(self, button: QPushButton, icon_name: str, fallback_text: str) -> None:
        set_action_button_icon(button, icon_name, fallback_text, self.theme)

    def _refresh_action_icons(self) -> None:
        if not hasattr(self, "add_button"):
            return
        self._set_action_button_icon(self.add_button, "fa6s.plus", "New")
        self._set_action_button_icon(self.refresh_button, "fa6s.arrows-rotate", "Ref")
        self._set_action_button_icon(self.history_button, "fa6s.clock-rotate-left", "His")
        self._set_action_button_icon(self.close_detail_button, "fa6s.xmark", "X")
        self.clear_search_action.setIcon(themed_icon("fa6s.xmark", self.theme))

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        self.task_detail_title_label = self._section_label("")
        self.close_detail_button = self._icon_button("", "fa6s.xmark", "X", self.close_task_detail)
        header_row.addWidget(self.task_detail_title_label)
        header_row.addStretch()
        header_row.addWidget(self.close_detail_button)
        layout.addLayout(header_row)

        self.detail_animation = QPropertyAnimation(panel, b"maximumWidth", self)
        self.detail_animation.setDuration(180)
        self.detail_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.detail_animation_closes = False

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.status_combo = QComboBox()
        self.priority_combo = QComboBox()
        self.project_combo = QComboBox()
        self.due_editor = DueDateEditor(due_day_end=self.due_day_end, language=self.language)

        for status, label in STATUS_LABELS.items():
            self.status_combo.addItem(label, status)
        for priority in PRIORITY_LABELS:
            self.priority_combo.addItem("", priority)

        form = QFormLayout()
        self.title_label = required_label("")
        self.description_label = QLabel()
        self.status_label = QLabel()
        self.priority_label = QLabel()
        self.project_label = QLabel()
        self.due_label = QLabel()
        form.addRow(self.title_label, self.title_edit)
        form.addRow(self.description_label, self.description_edit)
        form.addRow(self.status_label, self.status_combo)
        form.addRow(self.priority_label, self.priority_combo)
        form.addRow(self.project_label, self.project_combo)
        form.addRow(self.due_label, self.due_editor)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.save_button = QPushButton()
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_selected_task)
        self.complete_button = QPushButton()
        self.complete_button.setObjectName("SecondaryButton")
        self.complete_button.clicked.connect(self.complete_selected_task)
        self.task_delete_button = QPushButton()
        self.task_delete_button.setObjectName("DangerButton")
        self.task_delete_button.clicked.connect(self.delete_selected_task)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.complete_button)
        button_row.addWidget(self.task_delete_button)
        layout.addLayout(button_row)

        layout.addStretch()
        return panel

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def retranslate_ui(self) -> None:
        self.setWindowTitle("MindTask")
        self.tasks_nav_button.setText(self.tr("tasks"))
        self.projects_nav_button.setText(self.tr("projects"))
        self.settings_nav_button.setText(self.tr("settings"))

        self.search_edit.setPlaceholderText(self.tr("search_tasks"))
        self.clear_search_action.setToolTip(self.tr("clear_search"))
        self.sidebar_projects_label.setText(self.tr("projects"))
        self.tasks_title_label.setText(self.tr("tasks"))
        self.add_button.setToolTip(self.tr("new_task"))
        self.add_button.setAccessibleName(self.tr("new_task"))
        self.refresh_button.setToolTip(self.tr("refresh"))
        self.refresh_button.setAccessibleName(self.tr("refresh"))
        self.history_button.setToolTip(self.tr("history"))
        self.history_button.setAccessibleName(self.tr("history"))
        self.close_detail_button.setToolTip(self.tr("close"))
        self.close_detail_button.setAccessibleName(self.tr("close"))
        self.task_table.setHorizontalHeaderLabels(
            ["ID", self.tr("title"), self.tr("status"), self.tr("priority"), self.tr("project"), self.tr("due")]
        )
        self._update_task_sort_indicator()
        self.empty_label.setText(self.tr("no_tasks"))
        self.task_detail_title_label.setText(self.tr("task_detail"))
        self.title_label.setText(f'{self.tr("title")} <span style="color:#dc2626;">*</span>')
        self.description_label.setText(self.tr("description"))
        self.status_label.setText(self.tr("status"))
        self.priority_label.setText(self.tr("priority"))
        self.project_label.setText(self.tr("project"))
        self.due_label.setText(self.tr("due"))
        self.save_button.setText(self.tr("save"))
        self.complete_button.setText(self.tr("completed"))
        self.task_delete_button.setText(self.tr("delete"))

        self.projects_title_label.setText(self.tr("projects"))
        self.new_project_button.setText(self.tr("new_project"))
        self.rename_project_button.setText(self.tr("rename"))
        self.delete_project_button.setText(self.tr("delete"))
        self.projects_table.setHorizontalHeaderLabels(
            ["ID", self.tr("name"), self.tr("tasks"), self.tr("active"), self.tr("completed")]
        )
        self._update_project_sort_indicator()

        self.retranslate_settings_ui()
        self._retranslate_choice_controls()
        self.due_editor.retranslate(self.language)

    def _retranslate_choice_controls(self) -> None:
        current_status = self.status_combo.currentData()
        self.status_combo.blockSignals(True)
        for index in range(self.status_combo.count()):
            value = self.status_combo.itemData(index)
            self.status_combo.setItemText(index, self.tr(STATUS_TRANSLATION_KEYS.get(value, "status_not_started")))
        self.status_combo.blockSignals(False)
        if current_status is not None:
            self._set_status_combo(int(current_status))

        current_priority = self.priority_combo.currentData()
        self.priority_combo.blockSignals(True)
        for index in range(self.priority_combo.count()):
            value = self.priority_combo.itemData(index)
            self.priority_combo.setItemText(index, self.tr(PRIORITY_TRANSLATION_KEYS.get(value, "priority_none")))
        self.priority_combo.blockSignals(False)
        if current_priority is not None:
            self._set_priority_combo(int(current_priority))

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

    def open_task_detail(self) -> None:
        if not self.detail_panel.isHidden() and self.detail_panel.maximumWidth() > 0:
            return
        self.detail_animation.stop()
        if self.detail_animation_closes:
            self.detail_animation.finished.disconnect()
            self.detail_animation_closes = False
        self.detail_panel.show()
        self.detail_panel.setMinimumWidth(DETAIL_PANEL_MIN_WIDTH)
        self.detail_animation.setStartValue(max(0, self.detail_panel.maximumWidth()))
        self.detail_animation.setEndValue(DETAIL_PANEL_WIDTH)
        self.detail_animation.start()
        self.tasks_splitter.setSizes([SIDEBAR_WIDTH, 620, DETAIL_PANEL_WIDTH])

    def close_task_detail(self, clear_selection: bool = True) -> None:
        if not hasattr(self, "detail_panel"):
            return
        if clear_selection:
            self.selected_task_id = None
            self._clear_task_selection()
            self._clear_detail_panel()

        if self.detail_panel.isHidden():
            return

        self.detail_animation.stop()
        self.detail_animation.setStartValue(max(0, self.detail_panel.width()))
        self.detail_animation.setEndValue(0)
        if self.detail_animation_closes:
            self.detail_animation.finished.disconnect()
        self.detail_animation.finished.connect(self._hide_task_detail_after_animation)
        self.detail_animation_closes = True
        self.detail_animation.start()
        self.tasks_splitter.setSizes([SIDEBAR_WIDTH, 960, 0])

    def _hide_task_detail_after_animation(self) -> None:
        self.detail_panel.hide()
        self.detail_panel.setMaximumWidth(0)
        self.detail_panel.setMinimumWidth(0)
        if self.detail_animation_closes:
            self.detail_animation.finished.disconnect()
        self.detail_animation_closes = False

    def open_new_task_dialog(self) -> None:
        dialog = TaskDialog(self.db.get_projects(), self.language, self.due_day_end, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.task_data()
        try:
            task_id = self.db.create_task(**data)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_task"), str(exc))
            return

        self.refresh_all()
        self._select_task(task_id)

    def save_selected_task(self) -> None:
        if self.selected_task_id is None:
            return

        due_date = self.due_editor.due_value()
        try:
            normalize_due_date(due_date)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_due_date"), str(exc))
            return

        changed = self.db.update_task(
            self.selected_task_id,
            title=self.title_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            status=self.status_combo.currentData(),
            priority=self.priority_combo.currentData(),
            project_id=self.project_combo.currentData(),
            due_date=due_date,
        )
        if not changed:
            QMessageBox.warning(self, self.tr("save_failed"), self.tr("task_not_found"))
            return

        self.refresh_all()
        self.close_task_detail()

    def complete_selected_task(self) -> None:
        if self.selected_task_id is None:
            return
        self.db.complete_task(self.selected_task_id)
        self.refresh_all()
        self.close_task_detail()

    def delete_selected_task(self) -> None:
        if self.selected_task_id is None:
            return
        if not confirm_question(self, self.tr("delete_task"), self.tr("delete_task_confirm"), self.translator):
            return
        self.db.delete_task(self.selected_task_id)
        self.refresh_all()
        self.close_task_detail()

    def undo_last_operation(self) -> None:
        history = self.db.undo_last_operation()
        if not history:
            QMessageBox.information(self, self.tr("undo"), self.tr("no_operation_to_undo"))
            return
        self.refresh_all()

    def open_history_dialog(self) -> None:
        dialog = HistoryDialog(self.db, self.theme, self.language, parent=self)
        dialog.history_changed.connect(self.refresh_all)
        dialog.exec()

    def _apply_theme_to_app(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setProperty("mindtask_theme", theme)
            app.setStyleSheet(build_app_style(theme, app))

    def _clear_detail_panel(self) -> None:
        self.title_edit.clear()
        self.description_edit.clear()
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.project_combo.setCurrentIndex(0)
        self.due_editor.clear()

    def _set_status_combo(self, status: int) -> None:
        for index in range(self.status_combo.count()):
            if self.status_combo.itemData(index) == status:
                self.status_combo.setCurrentIndex(index)
                return
        self.status_combo.setCurrentIndex(0)

    def _set_priority_combo(self, priority: int) -> None:
        for index in range(self.priority_combo.count()):
            if self.priority_combo.itemData(index) == priority:
                self.priority_combo.setCurrentIndex(index)
                return
        self.priority_combo.setCurrentIndex(0)

    def _set_theme_combo(self, theme: str) -> None:
        for index in range(self.theme_combo.count()):
            if self.theme_combo.itemData(index) == theme:
                self.theme_combo.setCurrentIndex(index)
                return
        self.theme_combo.setCurrentIndex(0)

    def _set_due_day_end_combo(self, due_day_end: str) -> None:
        for index in range(self.due_day_end_combo.count()):
            if self.due_day_end_combo.itemData(index) == due_day_end:
                self.due_day_end_combo.setCurrentIndex(index)
                return
        self.due_day_end_combo.setCurrentIndex(0)

    def _set_project_combo(self, project_id: Optional[int]) -> None:
        for index in range(self.project_combo.count()):
            if self.project_combo.itemData(index) == project_id:
                self.project_combo.setCurrentIndex(index)
                return
        self.project_combo.setCurrentIndex(0)

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
