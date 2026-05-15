"""Settings page construction and handlers for the desktop window."""

from __future__ import annotations

import tempfile
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import (
    MindTaskDB,
    save_database_path,
    save_ui_due_day_end,
    save_ui_language,
    save_ui_theme,
)
from .constants import DUE_DAY_END_TRANSLATION_KEYS, THEME_TRANSLATION_KEYS
from .dialog_helpers import confirm_question
from .due_date_editor import DUE_DAY_END_OPTIONS
from .i18n import LANGUAGE_LABELS, LANGUAGE_OPTIONS
from .shortcut_settings import ShortcutSettingsMixin
from .style import THEME_OPTIONS


SIDEBAR_WIDTH = 220

class SettingsPageMixin(ShortcutSettingsMixin):
    """Mixin for settings UI layout and settings-specific commands."""

    def expanding_size_policy(self) -> QSizePolicy:
        return QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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

        general_panel = self._build_general_settings_panel()
        database_panel = self._build_database_settings_panel()
        shortcut_panel = self._build_shortcut_settings_panel()

        self.settings_stack.addWidget(self._settings_scroll_area(general_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(database_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(shortcut_panel))
        self.settings_section_list.setCurrentRow(0)
        return page

    def _build_general_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setSizePolicy(self.expanding_size_policy())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        self.general_settings_title_label = self._section_label("")
        layout.addWidget(self.general_settings_title_label)

        self.theme_combo = QComboBox()
        for theme in THEME_OPTIONS:
            self.theme_combo.addItem("", theme)
        self._set_theme_combo(self.theme)
        self.theme_combo.currentIndexChanged.connect(self.apply_theme_from_combo)
        self.theme_label = QLabel()
        form.addRow(self.theme_label, self.theme_combo)

        self.language_combo = QComboBox()
        for language in LANGUAGE_OPTIONS:
            self.language_combo.addItem(LANGUAGE_LABELS[language], language)
        self.language_combo.setCurrentIndex(list(LANGUAGE_OPTIONS).index(self.language))
        self.language_combo.currentIndexChanged.connect(self.apply_language_from_combo)
        self.language_label = QLabel()
        form.addRow(self.language_label, self.language_combo)

        self.due_day_end_combo = QComboBox()
        for option in DUE_DAY_END_OPTIONS:
            self.due_day_end_combo.addItem("", option)
        self._set_due_day_end_combo(self.due_day_end)
        self.due_day_end_combo.currentIndexChanged.connect(self.apply_due_day_end_from_combo)
        self.due_day_end_label = QLabel()
        form.addRow(self.due_day_end_label, self.due_day_end_combo)
        layout.addLayout(form)
        layout.addStretch()
        return panel

    def _build_database_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setSizePolicy(self.expanding_size_policy())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        self.data_settings_title_label = self._section_label("")
        layout.addWidget(self.data_settings_title_label)
        self.config_path_label = QLabel(self.config_path)
        self.config_path_label.setObjectName("MutedLabel")
        self.config_file_label = QLabel()
        form.addRow(self.config_file_label, self.config_path_label)

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
        form.addRow(self.database_path_label, database_path_row)
        layout.addLayout(form)

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
        layout.addLayout(button_row)
        layout.addStretch()
        return panel

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

    def show_inline_message(self, label: QLabel, message: str, timeout_ms: int = 3500) -> None:
        label.setText(message)
        label.setVisible(bool(message))
        if message:
            QTimer.singleShot(timeout_ms, label.hide)

    def retranslate_settings_ui(self) -> None:
        self.settings_sections_label.setText(self.tr("settings"))
        self._retranslate_settings_sections()
        self.general_settings_title_label.setText(self.tr("settings_general"))
        self.data_settings_title_label.setText(self.tr("settings_data"))
        self.theme_label.setText(self.tr("theme"))
        self.language_label.setText(self.tr("language"))
        self.due_day_end_label.setText(self.tr("due_day_end"))
        self.retranslate_shortcut_settings()
        self.config_file_label.setText(self.tr("config_file"))
        self.database_path_label.setText(self.tr("database_path"))
        self.apply_db_button.setText(self.tr("apply_database"))
        self.create_db_button.setText(self.tr("create_database"))
        self.reload_db_button.setText(self.tr("reload_current"))
        self.database_browse_button.setText(self.tr("browse"))
        self._retranslate_theme_combo()
        self._retranslate_due_day_end_combo()

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

    def switch_settings_section(self, index: int) -> None:
        index = max(0, min(index, self.settings_stack.count() - 1))
        self.settings_stack.setCurrentIndex(index)
        if self.settings_section_list.currentRow() != index:
            self.settings_section_list.setCurrentRow(index)

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
