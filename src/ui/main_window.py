"""Main desktop window for MindTask."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
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
    QScrollArea,
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

from ..core import (
    DEFAULT_UI_SHORTCUTS,
    MindTaskDB,
    get_config_path,
    normalize_due_date,
    save_database_path,
    save_ui_due_day_end,
    save_ui_language,
    save_ui_shortcuts,
    save_ui_theme,
)
from .constants import (
    DUE_DAY_END_TRANSLATION_KEYS,
    PRIORITY_LABELS,
    PRIORITY_TRANSLATION_KEYS,
    STATUS_LABELS,
    STATUS_TRANSLATION_KEYS,
    STATUS_VALUES,
    THEME_TRANSLATION_KEYS,
)
from .dialog_helpers import confirm_question, required_label
from .dialogs import HistoryDialog, ProjectDialog, TaskDialog
from .due_date_editor import DUE_DAY_END_OPTIONS, DueDateEditor
from .icons import icon_button, set_action_button_icon, themed_icon
from .i18n import LANGUAGE_LABELS, LANGUAGE_OPTIONS, Translator
from .style import THEME_OPTIONS, THEME_SYSTEM, badge_colors_for_theme, build_app_style, colors_for_theme


DETAIL_PANEL_MIN_WIDTH = 420
DETAIL_PANEL_WIDTH = 480
SIDEBAR_WIDTH = 220

SHORTCUT_ACTIONS = (
    ("open_tasks", "shortcut_open_tasks"),
    ("open_projects", "shortcut_open_projects"),
    ("open_settings", "shortcut_open_settings"),
    ("new_task", "shortcut_new_task_label"),
    ("focus_search", "shortcut_focus_search"),
    ("escape_tasks", "shortcut_escape_tasks"),
    ("refresh", "shortcut_refresh"),
    ("undo", "shortcut_undo"),
    ("history", "shortcut_history"),
    ("save_task", "shortcut_save_task"),
    ("complete_task", "shortcut_complete_task"),
    ("delete_task", "shortcut_delete_task"),
)


class ShortcutKeySequenceEdit(QLineEdit):
    keySequenceChanged = Signal(QKeySequence)
    focus_changed = Signal(bool)

    def __init__(self, sequence: QKeySequence):
        super().__init__()
        self._sequence = QKeySequence()
        self.setReadOnly(True)
        self.setKeySequence(sequence)

    def keySequence(self) -> QKeySequence:
        return self._sequence

    def setKeySequence(self, sequence: QKeySequence) -> None:
        self._sequence = sequence
        self.setText(sequence.toString(QKeySequence.SequenceFormat.NativeText))
        self.keySequenceChanged.emit(sequence)

    def focusInEvent(self, event: Any) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event: Any) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        if key in {
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
        }:
            event.accept()
            return
        if key == Qt.Key.Key_Backspace and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.setKeySequence(QKeySequence())
            event.accept()
            return
        modifiers = event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        self.setKeySequence(QKeySequence(modifiers.value | key))
        event.accept()

    def mousePressEvent(self, event: Any) -> None:
        self._accept_mouse_event(event)

    def mouseMoveEvent(self, event: Any) -> None:
        event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:
        event.accept()

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self._accept_mouse_event(event)

    def _accept_mouse_event(self, event: QEvent) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        event.accept()


class MindTaskWindow(QMainWindow):
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
            key_sequence = QKeySequence(sequence)
            if key_sequence.isEmpty():
                continue
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(handler)
            self.shortcuts.append(shortcut)

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

    def _build_tasks_page(self) -> QWidget:
        self.tasks_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tasks_splitter.addWidget(self._build_sidebar())
        self.tasks_splitter.addWidget(self._build_task_table())
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.setMaximumWidth(0)
        self.detail_panel.hide()
        self.tasks_splitter.addWidget(self.detail_panel)
        self.tasks_splitter.setSizes([SIDEBAR_WIDTH, 960, 0])
        return self.tasks_splitter

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.sidebar_projects_label = self._section_label("")
        layout.addWidget(self.sidebar_projects_label)
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

    def _build_projects_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        self.projects_title_label = self._section_label("")
        header_row.addWidget(self.projects_title_label)
        self.project_count_label = QLabel()
        self.project_count_label.setObjectName("MutedLabel")
        header_row.addStretch()
        header_row.addWidget(self.project_count_label)

        self.new_project_button = QPushButton()
        self.new_project_button.clicked.connect(self.open_new_project_dialog)
        self.rename_project_button = QPushButton()
        self.rename_project_button.setObjectName("SecondaryButton")
        self.rename_project_button.clicked.connect(self.open_rename_project_dialog)
        self.delete_project_button = QPushButton()
        self.delete_project_button.setObjectName("DangerButton")
        self.delete_project_button.clicked.connect(self.delete_selected_project)
        header_row.addWidget(self.new_project_button)
        header_row.addWidget(self.rename_project_button)
        header_row.addWidget(self.delete_project_button)
        layout.addWidget(header)

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

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        settings_body = QWidget()
        settings_body_layout = QHBoxLayout(settings_body)
        settings_body_layout.setContentsMargins(0, 0, 0, 0)
        settings_body_layout.setSpacing(0)
        settings_sidebar = QFrame()
        settings_sidebar.setObjectName("Sidebar")
        settings_sidebar.setMinimumWidth(SIDEBAR_WIDTH)
        settings_sidebar.setMaximumWidth(SIDEBAR_WIDTH)
        settings_nav = QVBoxLayout(settings_sidebar)
        settings_nav.setContentsMargins(14, 14, 14, 14)
        settings_nav.setSpacing(10)
        self.settings_sections_label = self._section_label("")
        settings_nav.addWidget(self.settings_sections_label)
        self.settings_section_list = QListWidget()
        self.settings_section_list.setObjectName("ProjectList")
        self.settings_section_list.currentRowChanged.connect(self.switch_settings_section)
        settings_nav.addWidget(self.settings_section_list, 1)

        self.settings_stack = QStackedWidget()
        settings_body_layout.addWidget(settings_sidebar)
        settings_body_layout.addWidget(self.settings_stack, 1)
        page_layout.addWidget(settings_body, 1)

        general_panel = QFrame()
        general_panel.setObjectName("DetailPanel")
        general_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        general_layout = QVBoxLayout(general_panel)
        general_layout.setContentsMargins(16, 16, 16, 16)
        general_layout.setSpacing(12)
        general_form = QFormLayout()
        self.general_settings_title_label = self._section_label("")
        general_layout.addWidget(self.general_settings_title_label)
        self.theme_combo = QComboBox()
        for theme in THEME_OPTIONS:
            self.theme_combo.addItem("", theme)
        self._set_theme_combo(self.theme)
        self.theme_combo.currentIndexChanged.connect(self.apply_theme_from_combo)
        self.theme_label = QLabel()
        general_form.addRow(self.theme_label, self.theme_combo)

        self.language_combo = QComboBox()
        for language in LANGUAGE_OPTIONS:
            self.language_combo.addItem(LANGUAGE_LABELS[language], language)
        self.language_combo.setCurrentIndex(list(LANGUAGE_OPTIONS).index(self.language))
        self.language_combo.currentIndexChanged.connect(self.apply_language_from_combo)
        self.language_label = QLabel()
        general_form.addRow(self.language_label, self.language_combo)

        self.due_day_end_combo = QComboBox()
        for option in DUE_DAY_END_OPTIONS:
            self.due_day_end_combo.addItem("", option)
        self._set_due_day_end_combo(self.due_day_end)
        self.due_day_end_combo.currentIndexChanged.connect(self.apply_due_day_end_from_combo)
        self.due_day_end_label = QLabel()
        general_form.addRow(self.due_day_end_label, self.due_day_end_combo)
        general_layout.addLayout(general_form)
        general_layout.addStretch()

        shortcut_panel = QFrame()
        shortcut_panel.setObjectName("DetailPanel")
        shortcut_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        shortcut_layout = QVBoxLayout(shortcut_panel)
        shortcut_layout.setContentsMargins(16, 16, 16, 16)
        shortcut_layout.setSpacing(12)
        shortcut_form = QFormLayout()
        self.shortcuts_title_label = self._section_label("")
        shortcut_layout.addWidget(self.shortcuts_title_label)
        self.shortcut_labels: Dict[str, QLabel] = {}
        self.shortcut_edits: Dict[str, ShortcutKeySequenceEdit] = {}
        self.shortcut_rows: Dict[str, QFrame] = {}
        self.shortcut_active_rows: set[str] = set()
        self.shortcut_cancel_buttons: Dict[str, QPushButton] = {}
        self.shortcut_default_buttons: Dict[str, QPushButton] = {}
        for action, _translation_key in SHORTCUT_ACTIONS:
            label = QLabel()
            row = QFrame()
            row.setObjectName("ShortcutRow")
            row.setProperty("shortcutModified", False)
            row.setProperty("shortcutActive", False)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)
            edit = ShortcutKeySequenceEdit(QKeySequence(self.shortcut_sequences.get(action, "")))
            edit.keySequenceChanged.connect(lambda _sequence, current_action=action: self.update_shortcut_row_state(current_action))
            edit.editingFinished.connect(lambda current_action=action: self.update_shortcut_row_state(current_action))
            edit.focus_changed.connect(lambda has_focus, current_action=action: self.update_shortcut_focus_state(current_action, has_focus))
            cancel_button = QPushButton()
            cancel_button.setObjectName("SecondaryButton")
            cancel_button.clicked.connect(lambda _checked=False, current_action=action: self.cancel_shortcut_change(current_action))
            default_button = QPushButton()
            default_button.setObjectName("SecondaryButton")
            default_button.clicked.connect(lambda _checked=False, current_action=action: self.reset_shortcut_to_default(current_action))
            row_layout.addWidget(edit, 1)
            row_layout.addWidget(cancel_button)
            row_layout.addWidget(default_button)
            self.shortcut_labels[action] = label
            self.shortcut_edits[action] = edit
            self.shortcut_rows[action] = row
            self.shortcut_cancel_buttons[action] = cancel_button
            self.shortcut_default_buttons[action] = default_button
            shortcut_form.addRow(label, row)
        shortcut_layout.addLayout(shortcut_form)

        shortcut_button_row = QWidget()
        shortcut_button_row.setObjectName("TransparentRow")
        shortcut_button_layout = QHBoxLayout(shortcut_button_row)
        shortcut_button_layout.setContentsMargins(0, 0, 0, 0)
        shortcut_button_layout.setSpacing(8)
        self.apply_shortcuts_button = QPushButton()
        self.apply_shortcuts_button.clicked.connect(self.apply_shortcuts_from_settings)
        self.reset_shortcuts_button = QPushButton()
        self.reset_shortcuts_button.setObjectName("SecondaryButton")
        self.reset_shortcuts_button.clicked.connect(self.reset_all_shortcuts_to_defaults)
        shortcut_button_layout.addWidget(self.apply_shortcuts_button)
        shortcut_button_layout.addWidget(self.reset_shortcuts_button)
        self.shortcuts_message = QLabel("")
        self.shortcuts_message.setObjectName("MutedLabel")
        self.shortcuts_message.hide()
        shortcut_button_layout.addWidget(self.shortcuts_message)
        shortcut_button_layout.addStretch()
        shortcut_layout.addWidget(shortcut_button_row)
        shortcut_layout.addStretch()

        database_panel = QFrame()
        database_panel.setObjectName("DetailPanel")
        database_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        database_layout = QVBoxLayout(database_panel)
        database_layout.setContentsMargins(16, 16, 16, 16)
        database_layout.setSpacing(12)
        database_form = QFormLayout()
        self.data_settings_title_label = self._section_label("")
        database_layout.addWidget(self.data_settings_title_label)
        self.config_path_label = QLabel(self.config_path)
        self.config_path_label.setObjectName("MutedLabel")
        self.config_file_label = QLabel()
        database_form.addRow(self.config_file_label, self.config_path_label)

        self.database_path_edit = QLineEdit(self.db.db_path)
        self.database_browse_button = QPushButton()
        self.database_browse_button.clicked.connect(self.browse_database_path)
        database_path_row = QWidget()
        database_path_row.setObjectName("TransparentRow")
        database_path_layout = QHBoxLayout(database_path_row)
        database_path_layout.setContentsMargins(0, 0, 0, 0)
        database_path_layout.setSpacing(8)
        database_path_layout.addWidget(self.database_path_edit, 1)
        database_path_layout.addWidget(self.database_browse_button)
        self.database_path_label = QLabel()
        database_form.addRow(self.database_path_label, database_path_row)
        database_layout.addLayout(database_form)

        button_row = QHBoxLayout()
        self.apply_db_button = QPushButton()
        self.apply_db_button.clicked.connect(self.apply_database_path)
        self.create_db_button = QPushButton()
        self.create_db_button.setObjectName("SecondaryButton")
        self.create_db_button.clicked.connect(self.create_database_from_settings)
        self.reload_db_button = QPushButton()
        self.reload_db_button.setObjectName("SecondaryButton")
        self.reload_db_button.clicked.connect(self.reload_current_database)
        button_row.addWidget(self.apply_db_button)
        button_row.addWidget(self.create_db_button)
        button_row.addWidget(self.reload_db_button)
        self.database_message = QLabel("")
        self.database_message.setObjectName("MutedLabel")
        self.database_message.hide()
        button_row.addWidget(self.database_message)
        button_row.addStretch()
        database_layout.addLayout(button_row)
        database_layout.addStretch()

        self.settings_stack.addWidget(self._settings_scroll_area(general_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(database_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(shortcut_panel))
        self.settings_section_list.setCurrentRow(0)
        return page

    def _settings_scroll_area(self, widget: QWidget) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget, 1)
        scroll_area.setWidget(content)
        return scroll_area

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def show_inline_message(self, label: QLabel, message: str, timeout_ms: int = 3500) -> None:
        label.setText(message)
        label.setVisible(bool(message))
        if message:
            QTimer.singleShot(timeout_ms, label.hide)

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

        self.settings_sections_label.setText(self.tr("settings"))
        self._retranslate_settings_sections()
        self.general_settings_title_label.setText(self.tr("settings_general"))
        self.data_settings_title_label.setText(self.tr("settings_data"))
        self.theme_label.setText(self.tr("theme"))
        self.language_label.setText(self.tr("language"))
        self.due_day_end_label.setText(self.tr("due_day_end"))
        self.shortcuts_title_label.setText(self.tr("keyboard_shortcuts"))
        for action, translation_key in SHORTCUT_ACTIONS:
            self.shortcut_labels[action].setText(self.tr(translation_key))
            self.shortcut_cancel_buttons[action].setText(self.tr("cancel_change"))
            self.shortcut_default_buttons[action].setText(self.tr("restore_default"))
            self.update_shortcut_row_state(action)
        self.apply_shortcuts_button.setText(self.tr("apply_shortcuts"))
        self.reset_shortcuts_button.setText(self.tr("reset_all_shortcuts"))
        self.config_file_label.setText(self.tr("config_file"))
        self.database_path_label.setText(self.tr("database_path"))
        self.apply_db_button.setText(self.tr("apply_database"))
        self.create_db_button.setText(self.tr("create_database"))
        self.reload_db_button.setText(self.tr("reload_current"))
        self.database_browse_button.setText(self.tr("browse"))
        self._retranslate_choice_controls()
        self._retranslate_theme_combo()
        self._retranslate_due_day_end_combo()
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

    def _retranslate_theme_combo(self) -> None:
        current_theme = self.theme_combo.currentData()
        self.theme_combo.blockSignals(True)
        for index in range(self.theme_combo.count()):
            value = self.theme_combo.itemData(index)
            self.theme_combo.setItemText(index, self.tr(THEME_TRANSLATION_KEYS.get(value, "theme_system")))
        self.theme_combo.blockSignals(False)
        if isinstance(current_theme, str):
            self._set_theme_combo(current_theme)

    def _retranslate_due_day_end_combo(self) -> None:
        current_value = self.due_day_end_combo.currentData()
        self.due_day_end_combo.blockSignals(True)
        for index in range(self.due_day_end_combo.count()):
            value = self.due_day_end_combo.itemData(index)
            self.due_day_end_combo.setItemText(
                index,
                self.tr(DUE_DAY_END_TRANSLATION_KEYS.get(value, "due_day_end_same_day")),
            )
        self.due_day_end_combo.blockSignals(False)
        if isinstance(current_value, str):
            self._set_due_day_end_combo(current_value)

    def _retranslate_settings_sections(self) -> None:
        current_row = max(0, self.settings_section_list.currentRow())
        labels = [
            self.tr("settings_general"),
            self.tr("settings_data"),
            self.tr("keyboard_shortcuts"),
        ]
        self.settings_section_list.blockSignals(True)
        self.settings_section_list.clear()
        for index, label in enumerate(labels):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._apply_list_item_color(item)
            self.settings_section_list.addItem(item)
        self.settings_section_list.setCurrentRow(min(current_row, len(labels) - 1))
        self.settings_section_list.blockSignals(False)
        self.switch_settings_section(self.settings_section_list.currentRow())

    def refresh_all(self) -> None:
        self.refresh_projects()
        self.refresh_project_table()
        self.refresh_tasks()

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
        if self._is_task_detail_open():
            self.close_task_detail()
            return
        self.clear_search()

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

    def switch_settings_section(self, index: int) -> None:
        index = max(0, min(index, self.settings_stack.count() - 1))
        self.settings_stack.setCurrentIndex(index)
        if self.settings_section_list.currentRow() != index:
            self.settings_section_list.setCurrentRow(index)

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
        self.due_editor.set_due_value(task.get("due_date"))
        self.open_task_detail()

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
        try:
            changed = self.db.update_project(project_id, name=dialog.project_name())
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

    def apply_theme(self, theme: str) -> None:
        self.theme = theme
        self._apply_theme_to_app(theme)
        self._refresh_action_icons()
        try:
            save_ui_theme(theme, self.config_path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("theme"), self.tr("could_not_save_theme", error=exc))
        self.refresh_tasks()

    def apply_theme_from_combo(self) -> None:
        theme = self.theme_combo.currentData()
        if isinstance(theme, str):
            self.apply_theme(theme)

    def apply_language_from_combo(self) -> None:
        language = self.language_combo.currentData()
        if not isinstance(language, str):
            return
        self.language = language
        self.translator.set_language(language)
        try:
            save_ui_language(language, self.config_path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("language"), self.tr("could_not_save_language", error=exc))
        self.retranslate_ui()
        self.refresh_all()

    def apply_due_day_end_from_combo(self) -> None:
        due_day_end = self.due_day_end_combo.currentData()
        if not isinstance(due_day_end, str):
            return
        self.due_day_end = due_day_end
        self.due_editor.set_due_day_end(due_day_end)
        try:
            save_ui_due_day_end(due_day_end, self.config_path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("settings"), self.tr("could_not_save_due_day_end", error=exc))

    def apply_shortcuts_from_settings(self) -> None:
        shortcuts = self._shortcut_settings_sequences()
        duplicate = self._first_duplicate_shortcut(shortcuts)
        if duplicate:
            QMessageBox.warning(
                self,
                self.tr("keyboard_shortcuts"),
                self.tr("duplicate_shortcut", shortcut=duplicate),
            )
            return
        try:
            save_ui_shortcuts(shortcuts, self.config_path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("keyboard_shortcuts"), self.tr("could_not_save_shortcuts", error=exc))
            return
        self.shortcut_sequences = shortcuts
        self._build_shortcuts()
        self.update_shortcut_change_indicators()
        self.show_inline_message(self.shortcuts_message, self.tr("shortcuts_updated"))

    def cancel_shortcut_change(self, action: str) -> None:
        self.shortcut_edits[action].setKeySequence(QKeySequence(self.shortcut_sequences.get(action, "")))
        self.update_shortcut_row_state(action)

    def reset_shortcut_to_default(self, action: str) -> None:
        self.shortcut_edits[action].setKeySequence(QKeySequence(DEFAULT_UI_SHORTCUTS.get(action, "")))
        self.update_shortcut_row_state(action)

    def reset_all_shortcuts_to_defaults(self) -> None:
        for action, sequence in DEFAULT_UI_SHORTCUTS.items():
            self.shortcut_edits[action].setKeySequence(QKeySequence(sequence))
            self.update_shortcut_row_state(action)

    def update_shortcut_change_indicators(self) -> None:
        for action, _translation_key in SHORTCUT_ACTIONS:
            self.update_shortcut_row_state(action)

    def update_shortcut_row_state(self, action: str) -> None:
        is_modified = self._shortcut_edit_text(action) != self._saved_shortcut_text(action)
        self.shortcut_cancel_buttons[action].setEnabled(is_modified)
        self._set_shortcut_row_property(action, "shortcutModified", is_modified)

    def update_shortcut_focus_state(self, action: str, has_focus: bool) -> None:
        if has_focus:
            self.shortcut_active_rows.add(action)
        else:
            self.shortcut_active_rows.discard(action)
        self._set_shortcut_row_property(action, "shortcutActive", has_focus)

    def _set_shortcut_row_property(self, action: str, name: str, value: bool) -> None:
        row = self.shortcut_rows[action]
        row.setProperty(name, value)
        row.style().unpolish(row)
        row.style().polish(row)
        row.update()

    def _shortcut_edit_text(self, action: str) -> str:
        return self.shortcut_edits[action].keySequence().toString(QKeySequence.SequenceFormat.PortableText)

    def _saved_shortcut_text(self, action: str) -> str:
        return QKeySequence(self.shortcut_sequences.get(action, "")).toString(QKeySequence.SequenceFormat.PortableText)

    def _shortcut_settings_sequences(self) -> Dict[str, str]:
        shortcuts: Dict[str, str] = {}
        for action, _translation_key in SHORTCUT_ACTIONS:
            shortcuts[action] = self._shortcut_edit_text(action)
        return shortcuts

    def _first_duplicate_shortcut(self, shortcuts: Dict[str, str]) -> str:
        seen = set()
        for sequence in shortcuts.values():
            key_sequence = QKeySequence(sequence)
            if key_sequence.isEmpty():
                continue
            canonical = key_sequence.toString(QKeySequence.SequenceFormat.PortableText)
            if canonical in seen:
                return canonical
            seen.add(canonical)
        return ""

    def _apply_theme_to_app(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setProperty("mindtask_theme", theme)
            app.setStyleSheet(build_app_style(theme, app))

    def apply_database_path(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            QMessageBox.warning(self, self.tr("database"), self.tr("database_path_required"))
            return

        try:
            tested_db = self._open_database_from_path(database_path)
            tested_db.get_tasks(limit=1)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr("could_not_open_database", error=exc))
            return

        try:
            save_database_path(database_path, self.config_path)
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.show_inline_message(self.database_message, self.tr("database_updated"))
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr("database_opened_config_failed", error=exc))

    def browse_database_path(self) -> None:
        current = self.database_path_edit.text().strip() or self.db.db_path
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("use_existing_database"),
            str(Path(current).parent),
            "SQLite (*.db *.sqlite *.sqlite3);;All files (*)",
        )
        if path:
            self.database_path_edit.setText(path)

    def create_database_from_settings(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            QMessageBox.warning(self, self.tr("database"), self.tr("database_path_required"))
            return

        target = Path(database_path)
        if target.exists():
            QMessageBox.warning(self, self.tr("database"), self.tr("database_file_exists"))
            return

        if not confirm_question(
            self,
            self.tr("create_database"),
            self.tr("create_database_confirm"),
            self.translator,
        ):
            return

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            new_db = self._open_database_from_path(str(target))
            new_db.create_sample_data()
            new_db.get_tasks(limit=1)
            save_database_path(str(target), self.config_path)
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.show_inline_message(self.database_message, self.tr("database_created"))
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr("could_not_create_database", error=exc))

    def reload_current_database(self) -> None:
        try:
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.show_inline_message(self.database_message, self.tr("database_reloaded"))
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr("could_not_reload_database", error=exc))

    def _open_database_from_path(self, database_path: str) -> MindTaskDB:
        config = self.db.config
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".ini", delete=False) as fh:
            temp_config_path = fh.name
            fh.write("[database]\n")
            fh.write(f"path = {database_path}\n")
            fh.write("\n")
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
        self.due_editor.clear()

    def _clear_task_selection(self) -> None:
        selection_model = self.task_table.selectionModel()
        if selection_model is not None:
            selection_model.clearSelection()
            selection_model.clearCurrentIndex()
        self.task_table.clearSelection()

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

    def _select_sidebar_project(self, project_id: Optional[int]) -> None:
        for row in range(self.project_list.count()):
            item = self.project_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                self.project_list.setCurrentRow(row)
                return

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
