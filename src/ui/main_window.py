"""Main desktop window for MindTask."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QRect, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QIcon, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import (
    DatabaseInvalidError,
    DatabaseMissingError,
    MindTaskDB,
    get_config_path,
    normalize_due_date,
)
from .database_unavailable import DatabaseUnavailableDialog
from .shared.alert_message import ALERT_WARN, AlertMessage
from .shared.constants import (
    HISTORY_ENTITY_TRANSLATION_KEYS,
    PRIORITY_LABELS,
    PRIORITY_TRANSLATION_KEYS,
    HISTORY_ACTION_TRANSLATION_KEYS,
    STATUS_LABELS,
    STATUS_TRANSLATION_KEYS,
    STATUS_VALUES,
)
from .tasks.checklist_markdown import ChecklistMarkdown
from .tasks.checklist_panel import ChecklistPanelMixin
from .shared.dialog_helpers import confirm_question, required_label
from .tasks.due_date_editor import DueDateEditor
from .shared.icons import icon_button, set_action_button_icon, themed_icon
from .shared.i18n import Translator
from .shared.pagination import PaginationState
from .shared.pagination_controls import PaginationControls
from .tasks.markdown import render_markdown_html
from .tasks.project_page import ProjectPageMixin
from .settings.settings_page import SettingsPageMixin
from .shared.status_bar import StatusBarMixin
from .shared.style import badge_colors_for_theme, build_app_style, colors_for_theme
from .tasks.task_detail_state import TaskDetailStateMixin
from .tasks.task_page import TaskPageMixin
from .settings.shortcut_editor import SHIFTED_KEY_ALIASES


DETAIL_PANEL_WIDTH = 526
DETAIL_FIELD_WIDTH = 360
DETAIL_LABEL_WIDTH = 114
DETAIL_SECTION_WIDTH = DETAIL_PANEL_WIDTH - 28
DETAIL_ANIMATION_DURATION_MS = 240
SIDEBAR_WIDTH = 220
HISTORY_PAGE_SIZE = 100


class _DatabaseUnavailableHandled(Exception):
    """Internal control flow used to stop nested UI work after database selection starts."""


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse wheel changes in the detail drawer."""

    def __init__(self) -> None:
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: Any) -> None:
        event.ignore()


class MindTaskWindow(
    StatusBarMixin,
    TaskDetailStateMixin,
    ChecklistPanelMixin,
    SettingsPageMixin,
    ProjectPageMixin,
    TaskPageMixin,
    QMainWindow,
):
    """Task-focused desktop shell around the existing MindTask core."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = str(get_config_path(config_path))
        self.db = MindTaskDB(config_path=config_path, create_if_missing=False)
        self.tasks: List[Dict[str, Any]] = []
        self.selected_task_id: Optional[int] = None
        self.theme = self.db.config.ui_theme
        self.language = self.db.config.ui_language
        self.smart_task_sorting = self.db.config.smart_task_sorting
        self.hide_completed_tasks = self.db.config.hide_completed_tasks
        self.shortcut_sequences = dict(self.db.config.ui_shortcuts)
        self.task_sort_column = 0
        self.task_sort_order = Qt.SortOrder.AscendingOrder
        self.project_sort_column = 0
        self.project_sort_order = Qt.SortOrder.AscendingOrder
        self.task_pagination = PaginationState(page_size=50)
        self.history_pagination = PaginationState(page_size=HISTORY_PAGE_SIZE)
        self.history_rows: List[Dict[str, Any]] = []
        self.active_search_keyword = ""
        self._detail_original_values: Dict[str, object] = {}
        self.detail_mode = "closed"
        self._restoring_task_selection = False
        self._restoring_filter_selection = False
        self._database_guard_depth = 0
        self._accepted_task_view: Optional[str] = None
        self._accepted_project_filter: Optional[int] = None
        self.translator = Translator(self.language)
        self._apply_theme_to_app(self.theme)

        self.setWindowTitle("MindTask")
        self.setWindowIcon(QApplication.windowIcon())
        self.resize(1180, 720)

        self._build_layout()
        self._build_shortcuts()
        self.retranslate_ui()
        self.refresh_all()
        self.position_sidebar_action_button()
        QTimer.singleShot(0, self.position_sidebar_action_button)

    def handle_unavailable_database_if_needed(self, exc: Exception) -> bool:
        if not isinstance(exc, (DatabaseMissingError, DatabaseInvalidError)):
            return False
        reason = "missing" if isinstance(exc, DatabaseMissingError) else "invalid"
        dialog = DatabaseUnavailableDialog(
            config_path=self.config_path,
            database_path=str(exc),
            language=self.language,
            reason=reason,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return True
        try:
            self.db = MindTaskDB(config_path=self.config_path, create_if_missing=False)
            self.theme = self.db.config.ui_theme
            self.language = self.db.config.ui_language
            self.translator.set_language(self.language)
            self.retranslate_ui()
            self.refresh_all(force_detail=True)
        except Exception as next_exc:
            if not self.handle_unavailable_database_if_needed(next_exc):
                raise
        return True

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if hasattr(self, "manage_projects_button"):
            self.position_sidebar_action_button()
        if hasattr(self, "projects_drawer") and not self.projects_drawer.isHidden():
            self.projects_drawer.setGeometry(self._projects_drawer_open_geometry())
        if hasattr(self, "history_drawer") and not self.history_drawer.isHidden():
            self.history_drawer.setGeometry(self._history_drawer_open_geometry())

    def _build_layout(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.page_stack = QStackedWidget()
        self.tasks_page = self._build_tasks_page()
        self._build_projects_drawer_animation()
        self._build_history_drawer_animation()
        self.settings_page = self._build_settings_page()
        self.page_stack.addWidget(self.tasks_page)
        self.page_stack.addWidget(self.settings_page)
        layout.addWidget(self.page_stack, 1)
        layout.addWidget(self._build_bottom_navigation())
        self.setCentralWidget(root)

        self.setStatusBar(QStatusBar())

    def _build_shortcuts(self) -> None:
        handlers = {
            "open_tasks": lambda: self.switch_page(0),
            "open_projects": self.shortcut_open_projects,
            "open_settings": lambda: self.switch_page(1),
            "new_task": self.shortcut_new_task,
            "focus_search": self.shortcut_focus_search,
            "escape_tasks": self.shortcut_escape_tasks,
            "refresh": self.refresh_all,
            "history": self.open_history_dialog,
            "save_task": self.shortcut_save_task,
            "complete_task": self.shortcut_complete_task,
            "delete_task": self.shortcut_delete_task,
            "previous_page": self.shortcut_previous_page,
            "next_page": self.shortcut_next_page,
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
        self.settings_nav_button = QPushButton()
        self.settings_nav_button.setObjectName("NavButton")
        self.settings_nav_button.clicked.connect(lambda: self.switch_page(1))

        layout.addStretch()
        layout.addWidget(self.tasks_nav_button)
        layout.addWidget(self.settings_nav_button)
        layout.addStretch()
        return panel

    def _icon_button(self, tooltip: str, icon_name: str, fallback_text: str, handler: Any) -> QPushButton:
        return icon_button(tooltip, icon_name, fallback_text, self.theme, handler)

    def _set_action_button_icon(self, button: QPushButton, icon_name: str, fallback_text: str) -> None:
        set_action_button_icon(button, icon_name, fallback_text, self.theme)

    def _set_checklist_done_button_icon(self, button: QPushButton) -> None:
        if button.isChecked():
            set_action_button_icon(button, "fa6s.check", "OK", self.theme)
        else:
            button.setIcon(QIcon())
            button.setText("")

    def _refresh_action_icons(self) -> None:
        if not hasattr(self, "add_button"):
            return
        self._set_action_button_icon(self.add_button, "fa6s.plus", "New")
        self._set_action_button_icon(self.refresh_button, "fa6s.arrows-rotate", "Ref")
        self._set_action_button_icon(self.history_button, "fa6s.clock-rotate-left", "His")
        self._set_action_button_icon(self.manage_projects_button, "fa6s.sliders", "Mgr")
        if hasattr(self, "refresh_task_history_button"):
            self._set_action_button_icon(self.refresh_task_history_button, "fa6s.arrows-rotate", "Ref")
        if hasattr(self, "add_checklist_item_button"):
            self._set_action_button_icon(self.add_checklist_item_button, "fa6s.plus", "+")
        if hasattr(self, "checklist_items_layout"):
            for index in range(self.checklist_items_layout.count()):
                item = self.checklist_items_layout.itemAt(index)
                row = item.widget() if item is not None else None
                if row is not None and row.layout() is not None:
                    button_item = row.layout().itemAt(0)
                    button = button_item.widget() if button_item is not None else None
                    if isinstance(button, QPushButton) and button.objectName() == "ChecklistDoneButton":
                        self._set_checklist_done_button_icon(button)
        self._set_action_button_icon(self.close_detail_button, "fa6s.xmark", "X")
        self._set_action_button_icon(self.close_projects_drawer_button, "fa6s.xmark", "X")
        if hasattr(self, "close_history_drawer_button"):
            self._set_action_button_icon(self.close_history_drawer_button, "fa6s.xmark", "X")
        self.clear_search_action.setIcon(themed_icon("fa6s.xmark", self.theme))

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 0, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 14, 0)
        self.task_detail_title_label = self._section_label("")
        self.close_detail_button = self._icon_button("", "fa6s.xmark", "X", self.close_task_detail)
        header_row.addWidget(self.task_detail_title_label)
        header_row.addStretch()
        header_row.addWidget(self.close_detail_button)
        layout.addLayout(header_row)

        self.detail_animation = QPropertyAnimation(panel, b"maximumWidth", self)
        self.detail_animation.setDuration(DETAIL_ANIMATION_DURATION_MS)
        self.detail_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.detail_animation.valueChanged.connect(self._apply_task_detail_animation_width)
        self.detail_animation_opens = False
        self.detail_animation_closes = False

        self.title_edit = QLineEdit()
        self.description_container = QWidget()
        self.description_container.setObjectName("TransparentRow")
        description_layout = QVBoxLayout(self.description_container)
        description_layout.setContentsMargins(0, 0, 0, 0)
        description_layout.setSpacing(0)
        self.description_preview = QTextBrowser()
        self.description_preview.setObjectName("MarkdownPreview")
        self.description_preview.setOpenExternalLinks(True)
        self.description_preview.document().setDocumentMargin(0)
        self.description_preview.document().setIndentWidth(16)
        self.description_preview.setMinimumHeight(140)
        self.description_preview.viewport().setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.description_preview.installEventFilter(self)
        self.description_preview.viewport().installEventFilter(self)
        self.description_edit = QTextEdit()
        self.description_edit.setObjectName("MarkdownEditor")
        self.description_edit.setMinimumHeight(140)
        self.description_edit.installEventFilter(self)
        self.description_edit.viewport().installEventFilter(self)
        self.description_stack = QStackedWidget()
        self.description_stack.addWidget(self.description_preview)
        self.description_stack.addWidget(self.description_edit)
        description_layout.addWidget(self.description_stack)
        self.checklist_container = QWidget()
        self.checklist_container.setObjectName("TransparentRow")
        checklist_layout = QVBoxLayout(self.checklist_container)
        checklist_layout.setContentsMargins(0, 0, 0, 0)
        checklist_layout.setSpacing(6)
        checklist_header = QWidget()
        checklist_header.setObjectName("TransparentRow")
        checklist_header_layout = QHBoxLayout(checklist_header)
        checklist_header_layout.setContentsMargins(0, 0, 0, 0)
        checklist_header_layout.setSpacing(8)
        self.checklist_title_label = self._section_label("")
        self.checklist_progress_label = QLabel()
        self.checklist_progress_label.setObjectName("MutedLabel")
        self.checklist_source_label = QLabel()
        self.checklist_source_label.setObjectName("MutedLabel")
        self.add_checklist_item_button = self._icon_button(
            "",
            "fa6s.plus",
            "+",
            self.add_checklist_item_to_description,
        )
        self.add_checklist_item_button.setFixedSize(28, 28)
        self.add_checklist_item_button.setIconSize(QSize(15, 15))
        checklist_header_layout.addWidget(self.checklist_title_label)
        checklist_header_layout.addWidget(self.checklist_progress_label)
        checklist_header_layout.addWidget(self.checklist_source_label)
        checklist_header_layout.addStretch()
        checklist_header_layout.addWidget(self.add_checklist_item_button)
        self.checklist_items_widget = QWidget()
        self.checklist_items_widget.setObjectName("TransparentRow")
        self.checklist_items_layout = QVBoxLayout(self.checklist_items_widget)
        self.checklist_items_layout.setContentsMargins(0, 0, 0, 0)
        self.checklist_items_layout.setSpacing(4)
        self.checklist_empty_label = QLabel()
        self.checklist_empty_label.setObjectName("MutedLabel")
        checklist_layout.addWidget(checklist_header)
        checklist_layout.addWidget(self.checklist_items_widget)
        checklist_layout.addWidget(self.checklist_empty_label)
        self.status_combo = NoWheelComboBox()
        self.priority_combo = NoWheelComboBox()
        self.project_combo = NoWheelComboBox()
        self.due_editor = DueDateEditor(language=self.language)
        self.due_editor.setObjectName("DueDateEditor")
        self.due_alert_row = AlertMessage()
        self.created_at_value_label = QLabel()
        self.created_at_value_label.setObjectName("MutedLabel")
        self.updated_at_value_label = QLabel()
        self.updated_at_value_label.setObjectName("MutedLabel")
        self.completed_at_value_label = QLabel()
        self.completed_at_value_label.setObjectName("MutedLabel")
        self.completed_at_row = QWidget()
        self.completed_at_row.setObjectName("TransparentRow")
        completed_at_layout = QHBoxLayout(self.completed_at_row)
        completed_at_layout.setContentsMargins(0, 0, 0, 0)
        completed_at_layout.setSpacing(8)
        completed_at_layout.addWidget(self.completed_at_value_label)
        completed_at_layout.addStretch()
        self.task_history_header = QWidget()
        self.task_history_header.setObjectName("TransparentRow")
        task_history_header_layout = QHBoxLayout(self.task_history_header)
        task_history_header_layout.setContentsMargins(0, 0, 0, 0)
        task_history_header_layout.setSpacing(8)
        self.task_history_label = self._section_label("")
        self.refresh_task_history_button = self._icon_button(
            "",
            "fa6s.arrows-rotate",
            "Ref",
            self.refresh_task_detail_history,
        )
        self.refresh_task_history_button.setFixedSize(28, 28)
        self.refresh_task_history_button.setIconSize(QSize(15, 15))
        task_history_header_layout.addWidget(self.task_history_label)
        task_history_header_layout.addStretch()
        task_history_header_layout.addWidget(self.refresh_task_history_button)
        self.task_history_tree = QTreeWidget()
        self.task_history_tree.setObjectName("TaskHistoryTree")
        self.task_history_tree.setHeaderHidden(True)
        self.task_history_tree.setRootIsDecorated(True)
        self.task_history_tree.setAlternatingRowColors(False)
        self.task_history_tree.setMinimumHeight(130)
        self.task_history_tree.setMaximumHeight(190)

        self._set_detail_field_widths()

        for status, label in STATUS_LABELS.items():
            self.status_combo.addItem(label, status)
        for priority in PRIORITY_LABELS:
            self.priority_combo.addItem("", priority)
        self._connect_detail_change_signals()

        detail_scroll_content = QWidget()
        detail_scroll_content.setObjectName("TransparentRow")
        self.detail_scroll_layout = QVBoxLayout(detail_scroll_content)
        self.detail_scroll_layout.setContentsMargins(0, 0, 20, 0)
        self.detail_scroll_layout.setSpacing(10)

        form = QFormLayout()
        self.title_label = required_label("")
        self.description_label = QLabel()
        self.status_label = QLabel()
        self.priority_label = QLabel()
        self.project_label = QLabel()
        self.due_label = QLabel()
        self.due_alert_spacer_label = QLabel()
        self.created_at_label = QLabel()
        self.updated_at_label = QLabel()
        self.completed_at_label = QLabel()
        self._set_detail_label_widths()
        form.addRow(self.title_label, self.title_edit)
        form.addRow(self.description_label, self.description_container)
        form.addRow(self.checklist_container)
        form.addRow(self.status_label, self.status_combo)
        form.addRow(self.priority_label, self.priority_combo)
        form.addRow(self.project_label, self.project_combo)
        form.addRow(self.due_label, self.due_editor)
        form.addRow(self.due_alert_spacer_label, self.due_alert_row)
        form.addRow(self.created_at_label, self.created_at_value_label)
        form.addRow(self.updated_at_label, self.updated_at_value_label)
        form.addRow(self.completed_at_label, self.completed_at_row)
        self.detail_scroll_layout.addLayout(form)
        self.detail_scroll_layout.addWidget(self.task_history_header)
        self.detail_scroll_layout.addWidget(self.task_history_tree)
        self.detail_scroll_layout.addStretch()

        self.detail_action_bar = QWidget()
        self.detail_action_bar.setObjectName("DetailActionBar")
        button_row = QHBoxLayout(self.detail_action_bar)
        button_row.setContentsMargins(0, 10, 14, 0)
        button_row.setSpacing(8)
        self.save_button = QPushButton()
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_selected_task)
        self.create_continue_button = QPushButton()
        self.create_continue_button.setObjectName("SecondaryButton")
        self.create_continue_button.clicked.connect(self.create_task_and_continue)
        self.discard_button = QPushButton()
        self.discard_button.setObjectName("SecondaryButton")
        self.discard_button.clicked.connect(self.discard_selected_task_changes)
        self.complete_button = QPushButton()
        self.complete_button.setObjectName("SecondaryButton")
        self.complete_button.clicked.connect(self.complete_selected_task)
        completed_at_layout.addWidget(self.complete_button)
        self.task_delete_button = QPushButton()
        self.task_delete_button.setObjectName("DangerButton")
        self.task_delete_button.clicked.connect(self.delete_selected_task)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.create_continue_button)
        button_row.addWidget(self.discard_button)
        button_row.addWidget(self.task_delete_button)

        self.detail_scroll_area = QScrollArea()
        self.detail_scroll_area.setObjectName("DetailScrollArea")
        self.detail_scroll_area.setWidgetResizable(True)
        self.detail_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll_area.setWidget(detail_scroll_content)
        layout.addWidget(self.detail_scroll_area, 1)
        layout.addWidget(self.detail_action_bar)
        return panel

    def _connect_detail_change_signals(self) -> None:
        self.title_edit.textChanged.connect(self._update_detail_field_states)
        self.description_edit.textChanged.connect(self._update_detail_field_states)
        self.description_edit.textChanged.connect(self.refresh_checklist_from_description)
        self.status_combo.currentIndexChanged.connect(self._update_detail_field_states)
        self.priority_combo.currentIndexChanged.connect(self._update_detail_field_states)
        self.project_combo.currentIndexChanged.connect(self._update_detail_field_states)
        self.due_editor.time_mode_combo.currentIndexChanged.connect(self._update_detail_field_states)
        self.due_editor.date_edit.dateChanged.connect(self._update_detail_field_states)
        self.due_editor.time_combo.currentTextChanged.connect(self._update_detail_field_states)

    def _set_detail_field_widths(self) -> None:
        for widget in (
            self.title_edit,
            self.description_container,
            self.status_combo,
            self.priority_combo,
            self.project_combo,
            self.due_editor,
            self.completed_at_row,
        ):
            widget.setMaximumWidth(DETAIL_FIELD_WIDTH)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, widget.sizePolicy().verticalPolicy())
        for widget in (self.task_history_header, self.task_history_tree):
            widget.setMaximumWidth(DETAIL_SECTION_WIDTH)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, widget.sizePolicy().verticalPolicy())

    def _set_detail_label_widths(self) -> None:
        for label in (
            self.title_label,
            self.description_label,
            self.status_label,
            self.priority_label,
            self.project_label,
            self.due_label,
            self.due_alert_spacer_label,
            self.created_at_label,
            self.updated_at_label,
            self.completed_at_label,
        ):
            label.setFixedWidth(DETAIL_LABEL_WIDTH)

    def _build_history_drawer(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QWidget()
        header.setObjectName("TransparentRow")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        self.history_drawer_title_label = self._section_label("")
        header_row.addWidget(self.history_drawer_title_label)
        header_row.addStretch()
        self.close_history_drawer_button = self._icon_button("", "fa6s.xmark", "X", self.close_history_drawer)
        header_row.addWidget(self.close_history_drawer_button)
        layout.addWidget(header)

        self.history_drawer_table = QTableWidget(0, 6)
        self.history_drawer_table.setObjectName("TaskTable")
        self.history_drawer_table.setHorizontalHeaderLabels(["ID", "", "", "", "", ""])
        self.history_drawer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_drawer_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_drawer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_drawer_table.verticalHeader().setVisible(False)
        self.history_drawer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_drawer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_drawer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_drawer_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_drawer_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_drawer_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_drawer_table, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        self.history_undo_latest_button = QPushButton()
        self.history_undo_latest_button.setObjectName("SecondaryButton")
        self.history_undo_latest_button.clicked.connect(self.undo_latest_from_history_drawer)
        self.history_undo_to_selected_button = QPushButton()
        self.history_undo_to_selected_button.setObjectName("DangerButton")
        self.history_undo_to_selected_button.clicked.connect(self.undo_to_selected_from_history_drawer)
        self.history_undo_warning_label = AlertMessage()
        self.history_pagination_controls = PaginationControls(self._icon_button)
        self.history_pagination_controls.previousRequested.connect(self.previous_history_page)
        self.history_pagination_controls.nextRequested.connect(self.next_history_page)
        self.history_pagination_controls.pageRequested.connect(self.jump_to_history_page)
        button_row.addWidget(self.history_undo_latest_button)
        button_row.addWidget(self.history_undo_to_selected_button)
        button_row.addWidget(self.history_undo_warning_label)
        button_row.addStretch()
        button_row.addWidget(self.history_pagination_controls)
        layout.addLayout(button_row)
        return panel

    def _build_projects_drawer_animation(self) -> None:
        self.projects_drawer_animation = QPropertyAnimation(self.projects_drawer, b"geometry", self)
        self.projects_drawer_animation.setDuration(DETAIL_ANIMATION_DURATION_MS)
        self.projects_drawer_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.projects_drawer_animation_opens = False
        self.projects_drawer_animation_closes = False

    def _build_history_drawer_animation(self) -> None:
        self.history_drawer_animation = QPropertyAnimation(self.history_drawer, b"geometry", self)
        self.history_drawer_animation.setDuration(DETAIL_ANIMATION_DURATION_MS)
        self.history_drawer_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.history_drawer_animation_opens = False
        self.history_drawer_animation_closes = False

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def retranslate_ui(self) -> None:
        self.setWindowTitle("MindTask")
        self.tasks_nav_button.setText(self.tr("tasks"))
        self.settings_nav_button.setText(self.tr("settings"))

        self.search_edit.setPlaceholderText(self.tr("search_tasks"))
        self.clear_search_action.setToolTip(self.tr("clear_search"))
        self.sidebar_views_label.setText(self.tr("due_filters"))
        self.sidebar_projects_label.setText(self.tr("projects"))
        self.manage_projects_button.setToolTip(self.tr("projects"))
        self.manage_projects_button.setAccessibleName(self.tr("projects"))
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
        self.task_detail_title_label.setText(self.tr("new_task") if self.detail_mode == "create" else self.tr("task_detail"))
        self.title_label.setText(f'{self.tr("title")} <span style="color:#dc2626;">*</span>')
        self.description_label.setText(self.tr("details"))
        self.status_label.setText(self.tr("status"))
        self.priority_label.setText(self.tr("priority"))
        self.project_label.setText(self.tr("project"))
        self.due_label.setText(self.tr("due"))
        self.created_at_label.setText(self.tr("created_at"))
        self.updated_at_label.setText(self.tr("updated_at"))
        self.completed_at_label.setText(self.tr("completed_at"))
        self.task_history_label.setText(self.tr("task_history"))
        self.refresh_task_history_button.setToolTip(self.tr("refresh"))
        self.refresh_task_history_button.setAccessibleName(self.tr("refresh"))
        self.checklist_title_label.setText(self.tr("checklist"))
        self.checklist_source_label.setText(self.tr("checklist_source_detail"))
        self.add_checklist_item_button.setToolTip(self.tr("add_checklist_item"))
        self.add_checklist_item_button.setAccessibleName(self.tr("add_checklist_item"))
        self.checklist_empty_label.setText(self.tr("no_checklist_items"))
        self.refresh_checklist_from_description()
        self.save_button.setText(self.tr("create_task") if self.detail_mode == "create" else self.tr("save"))
        self.create_continue_button.setText(self.tr("create_and_continue"))
        self.discard_button.setText(self.tr("cancel"))
        self.complete_button.setText(self.tr("mark_done"))
        self.task_delete_button.setText(self.tr("delete"))
        self.history_drawer_title_label.setText(self.tr("operation_history"))
        self.close_history_drawer_button.setToolTip(self.tr("close"))
        self.close_history_drawer_button.setAccessibleName(self.tr("close"))
        self.history_drawer_table.setHorizontalHeaderLabels(
            ["ID", self.tr("created"), self.tr("action"), self.tr("entity"), self.tr("state"), self.tr("undone")]
        )
        self.history_pagination_controls.set_tooltips(
            self.tr("previous_page"),
            self.tr("next_page"),
            self.tr("page_jump"),
        )
        self.history_undo_latest_button.setText(self.tr("undo_latest"))
        self.history_undo_to_selected_button.setText(self.tr("undo_to_selected"))
        self.history_undo_warning_label.set_message(self.tr("undo_warning"), ALERT_WARN)

        self.projects_title_label.setText(self.tr("projects"))
        self.close_projects_drawer_button.setToolTip(self.tr("close"))
        self.close_projects_drawer_button.setAccessibleName(self.tr("close"))
        self.new_project_button.setText(self.tr("new_project"))
        self.rename_project_button.setText(self.tr("rename"))
        self.delete_project_button.setText(self.tr("delete"))
        self.projects_table.setHorizontalHeaderLabels(
            ["ID", self.tr("name"), self.tr("tasks"), self.tr("active"), self.tr("completed")]
        )
        self.task_pagination_controls.set_tooltips(
            self.tr("previous_page"),
            self.tr("next_page"),
            self.tr("page_jump"),
        )
        self._update_project_sort_indicator()

        self.retranslate_settings_ui()
        self._retranslate_choice_controls()
        self.due_editor.retranslate(self.language)
        self.refresh_current_task_detail_text()

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

    def refresh_all(self, force_detail: bool = False) -> bool:
        if not self.confirm_task_detail_transition(force=force_detail):
            return False
        self.refresh_projects()
        self.refresh_project_table()
        self.refresh_tasks(force_detail=True)
        return True

    def switch_page(self, index: int) -> None:
        index = max(0, min(index, self.page_stack.count() - 1))
        if index != 0 and self._is_tasks_page():
            if not self.close_task_page_drawers():
                return
        self.page_stack.setCurrentIndex(index)
        if index == 0:
            self.tasks_nav_button.setObjectName("NavButtonActive")
            self.settings_nav_button.setObjectName("NavButton")
            self.refresh_tasks(force_detail=True)
        elif index == 1:
            self.tasks_nav_button.setObjectName("NavButton")
            self.settings_nav_button.setObjectName("NavButtonActive")
            self.show_settings_status()
        self.tasks_nav_button.style().unpolish(self.tasks_nav_button)
        self.tasks_nav_button.style().polish(self.tasks_nav_button)
        self.settings_nav_button.style().unpolish(self.settings_nav_button)
        self.settings_nav_button.style().polish(self.settings_nav_button)

    def close_task_page_drawers(self) -> bool:
        if self._is_task_detail_open() or not self.detail_panel.isHidden():
            if not self.close_task_detail(clear_selection=True):
                return False
        if self._is_projects_drawer_open():
            self.close_projects_drawer()
        if self._is_history_drawer_open():
            self.close_history_drawer()
        return True

    def close_task_page_drawers_before_opening(self, drawer: str) -> bool:
        if drawer != "projects" and self._is_projects_drawer_open():
            self.close_projects_drawer()
        if drawer != "history" and self._is_history_drawer_open():
            self.close_history_drawer()
        if self._is_task_detail_open() or not self.detail_panel.isHidden():
            if not self.close_task_detail(clear_selection=False):
                return False
        return True

    def open_projects_drawer(self) -> None:
        if not self._is_tasks_page() or self._is_projects_drawer_open():
            return
        if not self.close_task_page_drawers_before_opening("projects"):
            return
        self.projects_drawer_animation.stop()
        if self.projects_drawer_animation_opens or self.projects_drawer_animation_closes:
            self.projects_drawer_animation.finished.disconnect()
            self.projects_drawer_animation_opens = False
            self.projects_drawer_animation_closes = False
        self.projects_drawer.show()
        self.refresh_project_table()
        self.projects_drawer.raise_()
        start_geometry = self._projects_drawer_hidden_geometry()
        self.projects_drawer.setGeometry(start_geometry)
        self.projects_drawer_animation.setStartValue(start_geometry)
        self.projects_drawer_animation.setEndValue(self._projects_drawer_open_geometry())
        self.projects_drawer_animation.finished.connect(self._finish_open_projects_drawer)
        self.projects_drawer_animation_opens = True
        self.projects_drawer_animation.start()

    def close_projects_drawer(self) -> None:
        if not hasattr(self, "projects_drawer") or self.projects_drawer.isHidden():
            return
        self.projects_drawer_animation.stop()
        if self.projects_drawer_animation_opens:
            self.projects_drawer_animation.finished.disconnect()
            self.projects_drawer_animation_opens = False
        self.projects_drawer_animation.setStartValue(self.projects_drawer.geometry())
        self.projects_drawer_animation.setEndValue(self._projects_drawer_hidden_geometry())
        if self.projects_drawer_animation_closes:
            self.projects_drawer_animation.finished.disconnect()
        self.projects_drawer_animation.finished.connect(self._hide_projects_drawer_after_animation)
        self.projects_drawer_animation_closes = True
        self.projects_drawer_animation.start()

    def _finish_open_projects_drawer(self) -> None:
        self.projects_drawer.setGeometry(self._projects_drawer_open_geometry())
        if self.projects_drawer_animation_opens:
            self.projects_drawer_animation.finished.disconnect()
        self.projects_drawer_animation_opens = False

    def _hide_projects_drawer_after_animation(self) -> None:
        self.projects_drawer.hide()
        self.projects_drawer.setGeometry(self._projects_drawer_hidden_geometry())
        if self.projects_drawer_animation_closes:
            self.projects_drawer_animation.finished.disconnect()
        self.projects_drawer_animation_closes = False
        self.show_task_count_status()

    def _projects_drawer_open_geometry(self) -> QRect:
        width = max(0, self.tasks_page_container.width() - SIDEBAR_WIDTH)
        return QRect(SIDEBAR_WIDTH, 0, width, self.tasks_page_container.height())

    def _projects_drawer_hidden_geometry(self) -> QRect:
        open_geometry = self._projects_drawer_open_geometry()
        return QRect(self.tasks_page_container.width(), 0, open_geometry.width(), open_geometry.height())

    def open_history_drawer(self) -> None:
        if not self._is_tasks_page():
            self.switch_page(0)
        if self._is_history_drawer_open():
            self.history_drawer.raise_()
            return
        if not self.close_task_page_drawers_before_opening("history"):
            return
        self.history_drawer_animation.stop()
        if self.history_drawer_animation_opens or self.history_drawer_animation_closes:
            self.history_drawer_animation.finished.disconnect()
            self.history_drawer_animation_opens = False
            self.history_drawer_animation_closes = False
        self.history_drawer.show()
        self.refresh_history_drawer()
        self.history_drawer.raise_()
        start_geometry = self._history_drawer_hidden_geometry()
        self.history_drawer.setGeometry(start_geometry)
        self.history_drawer_animation.setStartValue(start_geometry)
        self.history_drawer_animation.setEndValue(self._history_drawer_open_geometry())
        self.history_drawer_animation.finished.connect(self._finish_open_history_drawer)
        self.history_drawer_animation_opens = True
        self.history_drawer_animation.start()

    def close_history_drawer(self) -> None:
        if not hasattr(self, "history_drawer") or self.history_drawer.isHidden():
            return
        self.history_drawer_animation.stop()
        if self.history_drawer_animation_opens:
            self.history_drawer_animation.finished.disconnect()
            self.history_drawer_animation_opens = False
        self.history_drawer_animation.setStartValue(self.history_drawer.geometry())
        self.history_drawer_animation.setEndValue(self._history_drawer_hidden_geometry())
        if self.history_drawer_animation_closes:
            self.history_drawer_animation.finished.disconnect()
        self.history_drawer_animation.finished.connect(self._hide_history_drawer_after_animation)
        self.history_drawer_animation_closes = True
        self.history_drawer_animation.start()

    def _finish_open_history_drawer(self) -> None:
        self.history_drawer.setGeometry(self._history_drawer_open_geometry())
        if self.history_drawer_animation_opens:
            self.history_drawer_animation.finished.disconnect()
        self.history_drawer_animation_opens = False

    def _hide_history_drawer_after_animation(self) -> None:
        self.history_drawer.hide()
        self.history_drawer.setGeometry(self._history_drawer_hidden_geometry())
        if self.history_drawer_animation_closes:
            self.history_drawer_animation.finished.disconnect()
        self.history_drawer_animation_closes = False
        self.show_task_count_status()

    def _history_drawer_open_geometry(self) -> QRect:
        width = max(0, self.tasks_page_container.width() - SIDEBAR_WIDTH)
        return QRect(SIDEBAR_WIDTH, 0, width, self.tasks_page_container.height())

    def _history_drawer_hidden_geometry(self) -> QRect:
        open_geometry = self._history_drawer_open_geometry()
        return QRect(self.tasks_page_container.width(), 0, open_geometry.width(), open_geometry.height())

    def open_task_detail(self) -> None:
        if not self.detail_panel.isHidden() and self.detail_panel.maximumWidth() > 0:
            return
        self.set_task_table_compact_mode(True)
        self.detail_animation.stop()
        if self.detail_animation_opens or self.detail_animation_closes:
            self.detail_animation.finished.disconnect()
            self.detail_animation_opens = False
            self.detail_animation_closes = False
        self.detail_panel.show()
        self.detail_panel.setMinimumWidth(0)
        self.detail_panel.setMaximumWidth(0)
        self._detail_animation_total_width = self.tasks_splitter.width()
        self._apply_task_detail_animation_width(0)
        self.detail_animation.setStartValue(max(0, self.detail_panel.maximumWidth()))
        self.detail_animation.setEndValue(DETAIL_PANEL_WIDTH)
        self.detail_animation.finished.connect(self._finish_open_task_detail)
        self.detail_animation_opens = True
        self.detail_animation.start()

    def close_task_detail(self, clear_selection: bool = True, force: bool = False) -> bool:
        if not hasattr(self, "detail_panel"):
            return True
        if not self.confirm_task_detail_transition(force=force):
            return False
        if clear_selection:
            self.selected_task_id = None
            self._clear_task_selection()
            self._clear_detail_panel()

        if self.detail_panel.isHidden():
            self.set_task_table_compact_mode(False)
            return True

        self.detail_animation.stop()
        if self.detail_animation_opens:
            self.detail_animation.finished.disconnect()
            self.detail_animation_opens = False
        self.detail_panel.setMinimumWidth(0)
        self._detail_animation_total_width = self.tasks_splitter.width()
        self.detail_animation.setStartValue(max(0, self.detail_panel.width()))
        self.detail_animation.setEndValue(0)
        if self.detail_animation_closes:
            self.detail_animation.finished.disconnect()
        self.detail_animation.finished.connect(self._hide_task_detail_after_animation)
        self.detail_animation_closes = True
        self.detail_animation.start()
        return True

    def confirm_task_detail_transition(self, force: bool = False) -> bool:
        if force or not self._is_task_detail_open() or not self._has_detail_changes():
            return True
        return confirm_question(
            self,
            self.tr("discard_task_changes"),
            self.tr("discard_task_changes_confirm"),
            self.translator,
        )

    def confirm_discard_task_detail_changes(self) -> bool:
        return self.confirm_task_detail_transition()

    def _apply_task_detail_animation_width(self, value: object) -> None:
        if not hasattr(self, "_detail_animation_total_width"):
            return
        total_width = self._detail_animation_total_width
        detail_width = max(0, min(int(value), DETAIL_PANEL_WIDTH, total_width - SIDEBAR_WIDTH))
        table_width = max(0, total_width - SIDEBAR_WIDTH - detail_width)
        self.tasks_splitter.setSizes([SIDEBAR_WIDTH, table_width, detail_width])

    def _finish_open_task_detail(self) -> None:
        self._apply_task_detail_animation_width(DETAIL_PANEL_WIDTH)
        self.detail_panel.setMinimumWidth(min(DETAIL_PANEL_WIDTH, max(0, self.tasks_splitter.width() - SIDEBAR_WIDTH)))
        if self.detail_animation_opens:
            self.detail_animation.finished.disconnect()
        self.detail_animation_opens = False

    def _hide_task_detail_after_animation(self) -> None:
        self._apply_task_detail_animation_width(0)
        self.detail_panel.hide()
        self.detail_panel.setMaximumWidth(0)
        self.detail_panel.setMinimumWidth(0)
        self.set_task_table_compact_mode(False)
        if self.selected_task_id is None:
            self.detail_mode = "closed"
        if self.detail_animation_closes:
            self.detail_animation.finished.disconnect()
        self.detail_animation_closes = False

    def open_new_task_dialog(self) -> None:
        if not self.confirm_task_detail_transition():
            return
        self.open_new_task_detail()

    def open_new_task_detail(self) -> None:
        self.selected_task_id = None
        self._clear_task_selection()
        self.detail_mode = "create"
        self._populate_new_task_detail()
        self.open_task_detail()
        self.title_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _populate_new_task_detail(self) -> None:
        self.task_detail_title_label.setText(self.tr("new_task"))
        self.title_edit.clear()
        self.description_edit.clear()
        self._show_description_preview()
        self._set_status_combo(0)
        self._set_priority_combo(0)
        self._set_project_combo(self._current_project_id() if hasattr(self, "project_list") else None)
        self.due_editor.clear()
        self._detail_original_values = self._empty_detail_values()
        self._set_create_detail_mode(True)
        self._update_detail_field_states()

    def save_selected_task(self) -> bool:
        due_date = self._validated_detail_due_date()
        if due_date is False:
            return False

        if self.detail_mode == "create":
            return self.create_task_from_detail(due_date)

        if self.selected_task_id is None:
            return False
        task_id = self.selected_task_id
        transitioning_to_completed = self._task_is_transitioning_to_completed()

        if transitioning_to_completed:
            completion_choice = self._confirm_incomplete_checklist_completion()
            if completion_choice == "cancel":
                return False
            if completion_choice == "complete_all_items":
                self._set_description_draft(ChecklistMarkdown(self.description_edit.toPlainText()).complete_all())

        changed = self.db.update_task(
            self.selected_task_id,
            title=self.title_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            status=self.status_combo.currentData(),
            priority=self.priority_combo.currentData(),
            project_id=self.project_combo.currentData(),
            due_date=due_date,
            due_mode=self.due_editor.due_mode(),
        )
        if not changed:
            QMessageBox.warning(self, self.tr("save_failed"), self.tr("task_not_found"))
            return False

        self.refresh_all(force_detail=True)
        self.close_task_detail(force=True)
        status_key = "status_task_completed" if transitioning_to_completed else "status_task_saved"
        self.show_task_operation_status(status_key, id=task_id)
        return True

    def _validated_detail_due_date(self) -> object:
        if not self.title_edit.text().strip():
            self._update_detail_field_states()
            QMessageBox.warning(self, self.tr("invalid_task"), self.tr("title_required"))
            return False

        date_invalid, time_invalid = self.due_editor.invalid_parts()
        if date_invalid or time_invalid:
            self._update_detail_field_states()
            message = self.tr("invalid_date") if date_invalid else self.tr("invalid_time")
            QMessageBox.warning(self, self.tr("invalid_due_date"), message)
            return False

        try:
            due_date = self.due_editor.due_value()
            normalize_due_date(due_date)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_due_date"), str(exc))
            return False

        return due_date

    def create_task_from_detail(self, due_date: Optional[str], continue_new: bool = False) -> bool:
        try:
            task_id = self.db.create_task(
                title=self.title_edit.text().strip(),
                description=self.description_edit.toPlainText().strip(),
                status=self.status_combo.currentData(),
                priority=self.priority_combo.currentData(),
                project_id=self.project_combo.currentData(),
                due_date=due_date,
                due_mode=self.due_editor.due_mode(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_task"), str(exc))
            return False
        self.detail_mode = "edit"
        self.selected_task_id = task_id
        self.refresh_all(force_detail=True)
        self._select_task(task_id)
        self.show_task_operation_status("status_task_created", id=task_id)
        if continue_new:
            self.open_new_task_detail()
        return True

    def create_task_and_continue(self) -> bool:
        if self.detail_mode != "create":
            return False
        due_date = self._validated_detail_due_date()
        if due_date is False:
            return False
        return self.create_task_from_detail(due_date, continue_new=True)

    def _task_is_transitioning_to_completed(self) -> bool:
        original_status = int(self._detail_original_values.get("status") or 0)
        current_status = int(self.status_combo.currentData() or 0)
        return original_status != 3 and current_status == 3

    def _confirm_incomplete_checklist_completion(self) -> str:
        items = ChecklistMarkdown(self.description_edit.toPlainText()).items()
        if not any(not item.completed for item in items):
            return "complete_task_only"

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(self.tr("unfinished_checklist"))
        dialog.setText(self.tr("unfinished_checklist_complete_prompt"))
        task_only_button = dialog.addButton(
            self.tr("complete_task_only"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        all_items_button = dialog.addButton(
            self.tr("complete_all_items"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_button = dialog.addButton(
            self.tr("cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == task_only_button:
            return "complete_task_only"
        if clicked == all_items_button:
            return "complete_all_items"
        return "cancel"

    def _show_description_editor(self) -> None:
        self.description_stack.setCurrentWidget(self.description_edit)
        self.description_edit.setFocus(Qt.FocusReason.MouseFocusReason)

    def _show_description_preview(self) -> None:
        self._update_description_preview()
        self.description_stack.setCurrentWidget(self.description_preview)
        self.description_preview.viewport().setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _is_description_editing(self) -> bool:
        return self.description_stack.currentWidget() == self.description_edit

    def _update_description_preview(self) -> None:
        self.description_preview.setHtml(render_markdown_html(self.description_edit.toPlainText()))
        self._compact_description_preview_lists()

    def _compact_description_preview_lists(self) -> None:
        seen_lists = set()
        block = self.description_preview.document().firstBlock()
        while block.isValid():
            text_list = block.textList()
            if text_list is not None and id(text_list) not in seen_lists:
                seen_lists.add(id(text_list))
                list_format = text_list.format()
                list_format.setIndent(max(1, list_format.indent()))
                text_list.setFormat(list_format)
            block = block.next()

    def _set_description_draft(self, markdown_text: str) -> None:
        cursor_position = self.description_edit.textCursor().position()
        self.description_edit.setPlainText(markdown_text)
        cursor = self.description_edit.textCursor()
        cursor.setPosition(min(cursor_position, len(markdown_text)))
        self.description_edit.setTextCursor(cursor)
        self._update_description_preview()
        self.refresh_checklist_from_description()
        self._update_detail_field_states()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched == self.description_preview.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if self.description_preview.anchorAt(event.position().toPoint()):
                return False
            self._show_description_editor()
            return True
        if watched in (self.description_preview, self.description_preview.viewport()) and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._show_description_editor()
                return True
        if watched in (self.description_edit, self.description_edit.viewport()) and event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._show_description_preview_if_editing)
        return super().eventFilter(watched, event)

    def _show_description_preview_if_editing(self) -> None:
        if self._is_description_editing():
            self._show_description_preview()

    def refresh_task_detail_history(self) -> None:
        self.task_history_tree.clear()
        if self.selected_task_id is None:
            return
        rows = self.db.get_task_history(self.selected_task_id, limit=10, include_undone=True)
        if not rows:
            item = QTreeWidgetItem([self.tr("no_task_history")])
            item.setDisabled(True)
            self.task_history_tree.addTopLevelItem(item)
            return
        for history in rows:
            changes = self._task_history_changes(history)
            summary = self._task_history_summary(history, changes)
            root = QTreeWidgetItem([summary])
            root.setData(0, Qt.ItemDataRole.UserRole, history.get("id"))
            self.task_history_tree.addTopLevelItem(root)
            if not changes:
                root.addChild(QTreeWidgetItem([self.tr("no_field_changes")]))
                continue
            for label, before, after in changes:
                if label == self.tr("details"):
                    root.addChild(QTreeWidgetItem([self.tr("details_changed")]))
                else:
                    root.addChild(QTreeWidgetItem([self.tr("field_changed", field=label, before=before, after=after)]))
        self.task_history_tree.expandToDepth(0)

    def _task_history_summary(self, history: Dict[str, Any], changes: List[tuple[str, str, str]]) -> str:
        created_at = self._format_detail_timestamp(history.get("created_at"))
        action = self.tr(HISTORY_ACTION_TRANSLATION_KEYS.get(str(history.get("action")), str(history.get("action"))))
        if history.get("undone_at"):
            action = f"{action} / {self.tr('undone')}"
        if not changes:
            return f"{created_at}  {action}"
        fields = ", ".join(change[0] for change in changes[:3])
        if len(changes) > 3:
            fields = self.tr("task_history_fields_more", fields=fields, count=len(changes) - 3)
        return f"{created_at}  {action}  {fields}"

    def _task_history_changes(self, history: Dict[str, Any]) -> List[tuple[str, str, str]]:
        before = self._history_task_snapshot(history.get("before_json"))
        after = self._history_task_snapshot(history.get("after_json"))
        changes: List[tuple[str, str, str]] = []
        fields = (
            ("title", self.tr("title")),
            ("description", self.tr("details")),
            ("status", self.tr("status")),
            ("priority", self.tr("priority")),
            ("project_id", self.tr("project")),
            ("due", self.tr("due")),
        )
        for key, label in fields:
            before_value = self._task_history_field_value(before, key)
            after_value = self._task_history_field_value(after, key)
            if before_value != after_value:
                changes.append((label, before_value, after_value))
        return changes

    def _history_task_snapshot(self, value: object) -> Optional[Dict[str, Any]]:
        if not value:
            return None
        try:
            data = json.loads(str(value))
        except json.JSONDecodeError:
            return None
        task = data.get("task") if isinstance(data, dict) else None
        return task if isinstance(task, dict) else None

    def _task_history_field_value(self, task: Optional[Dict[str, Any]], field: str) -> str:
        if task is None:
            return self.tr("none")
        if field == "status":
            return self.tr(STATUS_TRANSLATION_KEYS.get(int(task.get("status") or 0), "status_not_started"))
        if field == "priority":
            return self.tr(PRIORITY_TRANSLATION_KEYS.get(int(task.get("priority") or 0), "priority_none"))
        if field == "project_id":
            project_id = task.get("project_id")
            if project_id is None:
                return self.tr("none")
            for project in self.db.get_projects():
                if project.get("id") == project_id:
                    return project.get("name") or f"#{project_id}"
            return f"#{project_id}"
        if field == "due":
            due_date = task.get("due_date")
            due_mode = task.get("due_mode") or "none"
            if not due_date or due_mode == "none":
                return self.tr("none")
            if due_mode == "all_day":
                return f"{str(due_date)[:10]} {self.tr('all_day')}"
            return str(due_date)
        value = task.get(field)
        if value in (None, ""):
            return self.tr("none")
        return str(value)

    def complete_selected_task(self) -> None:
        if self.selected_task_id is None or self.detail_mode != "edit":
            return
        task = self.db.get_task(self.selected_task_id)
        if task and task.get("status") == 3:
            return
        previous_status = self.status_combo.currentData()
        self._set_status_combo(3)
        if not self.save_selected_task() and previous_status is not None:
            self._set_status_combo(int(previous_status))

    def delete_selected_task(self) -> None:
        if self.selected_task_id is None or self.detail_mode != "edit":
            return
        if not confirm_question(self, self.tr("delete_task"), self.tr("delete_task_confirm"), self.translator):
            return
        self.db.delete_task(self.selected_task_id)
        task_id = self.selected_task_id
        self.refresh_all(force_detail=True)
        self.close_task_detail(force=True)
        self.show_task_operation_status("status_task_deleted", id=task_id)

    def open_history_dialog(self) -> None:
        if self._is_tasks_page() and self._is_history_drawer_open():
            self.close_history_drawer()
            return
        self.open_history_drawer()

    def refresh_history_drawer(self) -> None:
        rows = self.db.get_history(include_undone=True)
        self.history_rows = rows
        visible_rows = self._history_page_items(rows)
        self.history_drawer_table.setRowCount(len(visible_rows))
        for row_index, history in enumerate(visible_rows):
            entity_id = f"#{history['entity_id']}" if history.get("entity_id") is not None else ""
            action = history["action"]
            entity_type = history["entity_type"]
            values = [
                history["id"],
                history["created_at"],
                self.tr(HISTORY_ACTION_TRANSLATION_KEYS.get(action, action)),
                f"{self.tr(HISTORY_ENTITY_TRANSLATION_KEYS.get(entity_type, entity_type))}{entity_id}",
                self.tr("undone") if history.get("undone_at") else self.tr("active"),
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
                self.history_drawer_table.setItem(row_index, column, item)
        self.history_drawer_table.resizeRowsToContents()
        self._update_history_pager(len(rows))
        self.history_undo_latest_button.setEnabled(any(not row.get("undone_at") for row in rows))
        self.history_undo_to_selected_button.setEnabled(bool(visible_rows))
        if self._is_history_drawer_open():
            self.show_history_count_status()

    def _history_page_items(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return list(self.history_pagination.items(rows))

    def _update_history_pager(self, total: int) -> None:
        self.history_pagination.set_total(total)
        self.history_pagination_controls.set_state(
            self.history_pagination,
            self.tr(
                "page_status",
                page=self.history_pagination.current_page,
                pages=self.history_pagination.total_pages,
            ),
        )

    def previous_history_page(self) -> None:
        self.history_drawer_table.clearSelection()
        self.history_pagination.previous()
        self.refresh_history_drawer()

    def next_history_page(self) -> None:
        self.history_drawer_table.clearSelection()
        self.history_pagination.next()
        self.refresh_history_drawer()

    def jump_to_history_page(self, page: int) -> None:
        self.history_drawer_table.clearSelection()
        self.history_pagination.set_current_page(page)
        self.refresh_history_drawer()

    def undo_latest_from_history_drawer(self) -> None:
        if not confirm_question(
            self,
            self.tr("undo_latest"),
            self.tr("undo_latest_confirm"),
            self.translator,
        ):
            return
        history = self.db.undo_last_operation()
        if not history:
            QMessageBox.information(self, self.tr("undo"), self.tr("no_operation_to_undo"))
            self.refresh_history_drawer()
            return
        self.refresh_all(force_detail=True)
        self.refresh_history_drawer()
        self.show_history_operation_status(1)

    def undo_to_selected_from_history_drawer(self) -> None:
        history_id = self._selected_history_drawer_id()
        if history_id is None:
            QMessageBox.information(self, self.tr("history"), self.tr("select_history_first"))
            return

        selected = self._selected_history_drawer_row()
        if selected is not None and selected.get("undone_at"):
            QMessageBox.information(self, self.tr("history"), self.tr("selected_history_undone"))
            return

        if not confirm_question(
            self,
            self.tr("undo_to_selected"),
            self.tr("undo_to_selected_confirm"),
            self.translator,
        ):
            return

        undone = self.db.undo_operations_until(history_id)
        if not undone:
            QMessageBox.information(self, self.tr("undo"), self.tr("no_operation_was_undone"))
            self.refresh_history_drawer()
            return

        self.refresh_all(force_detail=True)
        self.refresh_history_drawer()
        self.show_history_operation_status(len(undone))

    def _selected_history_drawer_id(self) -> Optional[int]:
        rows = self.history_drawer_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.history_drawer_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _selected_history_drawer_row(self) -> Optional[Dict[str, Any]]:
        history_id = self._selected_history_drawer_id()
        if history_id is None:
            return None
        for row in self.history_rows or self.db.get_history(include_undone=True):
            if row["id"] == history_id:
                return row
        return None

    def _apply_theme_to_app(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setProperty("mindtask_theme", theme)
            app.setStyleSheet(build_app_style(theme, app))

    def _clear_detail_panel(self) -> None:
        self._detail_original_values = {}
        self.detail_mode = "closed"
        self.title_edit.clear()
        self.description_edit.clear()
        self._show_description_preview()
        self.refresh_checklist_from_description()
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.project_combo.setCurrentIndex(0)
        self.due_editor.clear()
        self.task_detail_title_label.setText(self.tr("task_detail"))
        self.due_alert_row.clear_message()
        self.due_alert_spacer_label.hide()
        self.due_alert_row.hide()
        self.created_at_value_label.clear()
        self.updated_at_value_label.clear()
        self.completed_at_value_label.clear()
        self.complete_button.show()
        self.task_history_tree.clear()
        self._clear_detail_field_states()
        self._set_create_detail_mode(False)

    def _set_create_detail_mode(self, create_mode: bool) -> None:
        for widget in (
            self.due_alert_spacer_label,
            self.due_alert_row,
            self.created_at_label,
            self.created_at_value_label,
            self.updated_at_label,
            self.updated_at_value_label,
            self.completed_at_label,
            self.completed_at_row,
            self.task_history_header,
            self.task_history_tree,
            self.task_delete_button,
        ):
            widget.setVisible(not create_mode)
        self.create_continue_button.setVisible(create_mode)
        if create_mode:
            self.complete_button.hide()
            self.save_button.setText(self.tr("create_task"))
        else:
            self.save_button.setText(self.tr("save"))

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


def _with_unavailable_database_handler(method: Any) -> Any:
    def wrapped(self: MindTaskWindow, *args: object, **kwargs: object) -> object:
        self._database_guard_depth = getattr(self, "_database_guard_depth", 0) + 1
        try:
            return method(self, *args, **kwargs)
        except (DatabaseMissingError, DatabaseInvalidError) as exc:
            self.handle_unavailable_database_if_needed(exc)
            if self._database_guard_depth > 1:
                raise _DatabaseUnavailableHandled()
            return False
        except _DatabaseUnavailableHandled:
            if self._database_guard_depth > 1:
                raise
            return False
        finally:
            self._database_guard_depth = max(0, getattr(self, "_database_guard_depth", 1) - 1)

    return wrapped


for _method_name in (
    "refresh_all",
    "switch_page",
    "refresh_tasks",
    "refresh_projects",
    "refresh_project_table",
    "open_projects_drawer",
    "open_history_drawer",
    "refresh_history_drawer",
    "save_selected_task",
    "create_task_from_detail",
    "create_task_and_continue",
    "complete_selected_task",
    "delete_selected_task",
    "refresh_task_detail_history",
    "load_selected_task",
    "refresh_current_task_detail_text",
    "undo_latest_from_history_drawer",
    "undo_to_selected_from_history_drawer",
    "reload_current_database",
    "open_new_project_dialog",
    "open_rename_project_dialog",
    "delete_selected_project",
):
    setattr(MindTaskWindow, _method_name, _with_unavailable_database_handler(getattr(MindTaskWindow, _method_name)))
