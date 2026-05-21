"""Settings page construction and handlers for the desktop window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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

from .. import __author__, __version__
from ..core import (
    MindTaskDB,
    save_database_path,
    save_hide_completed_tasks,
    save_smart_task_sorting,
    save_ui_language,
    save_ui_theme,
)
from .alert_message import ALERT_DANGER, ALERT_INFO, AlertMessage
from .database_file_service import (
    DatabaseFileService,
    DatabasePathError,
)
from .constants import THEME_TRANSLATION_KEYS
from .dialog_helpers import confirm_question
from .i18n import LANGUAGE_LABELS, LANGUAGE_OPTIONS
from .shortcut_settings import ShortcutSettingsMixin
from .style import THEME_OPTIONS
from .toggle_switch import ToggleSwitch


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
        about_panel = self._build_about_settings_panel()

        self.settings_stack.addWidget(self._settings_scroll_area(general_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(database_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(shortcut_panel))
        self.settings_stack.addWidget(self._settings_scroll_area(about_panel))
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

        self.smart_task_sorting_checkbox = ToggleSwitch()
        self.smart_task_sorting_checkbox.setChecked(self.smart_task_sorting)
        self.smart_task_sorting_checkbox.toggled.connect(self.apply_smart_task_sorting_from_checkbox)
        self.smart_task_sorting_label = QLabel()
        smart_sorting_row = QWidget()
        smart_sorting_row.setObjectName("TransparentRow")
        smart_sorting_layout = QVBoxLayout(smart_sorting_row)
        smart_sorting_layout.setContentsMargins(0, 3, 0, 0)
        smart_sorting_layout.setSpacing(4)
        self.smart_task_sorting_hint_label = QLabel()
        self.smart_task_sorting_hint_label.setObjectName("MutedLabel")
        self.smart_task_sorting_hint_label.setWordWrap(True)
        smart_sorting_layout.addWidget(self.smart_task_sorting_checkbox)
        smart_sorting_layout.addWidget(self.smart_task_sorting_hint_label)
        form.addRow(self.smart_task_sorting_label, smart_sorting_row)

        self.hide_completed_tasks_checkbox = ToggleSwitch()
        self.hide_completed_tasks_checkbox.setChecked(self.hide_completed_tasks)
        self.hide_completed_tasks_checkbox.toggled.connect(self.apply_hide_completed_tasks_from_checkbox)
        self.hide_completed_tasks_label = QLabel()
        hide_completed_row = QWidget()
        hide_completed_row.setObjectName("TransparentRow")
        hide_completed_layout = QVBoxLayout(hide_completed_row)
        hide_completed_layout.setContentsMargins(0, 3, 0, 0)
        hide_completed_layout.setSpacing(4)
        hide_completed_layout.addWidget(self.hide_completed_tasks_checkbox)
        form.addRow(self.hide_completed_tasks_label, hide_completed_row)

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
        self.data_settings_title_label = self._section_label("")
        layout.addWidget(self.data_settings_title_label)

        current_form = QFormLayout()
        self.current_database_title_label = self._section_label("")
        layout.addWidget(self.current_database_title_label)
        self.current_database_path_label = QLabel()
        self.current_database_path_value_label = QLabel(self.db.db_path)
        self.current_database_path_value_label.setObjectName("MutedLabel")
        self.current_database_path_value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.current_database_path_value_label.setWordWrap(True)
        current_form.addRow(self.current_database_path_label, self.current_database_path_value_label)
        layout.addLayout(current_form)

        current_button_row = QHBoxLayout()
        self.reload_db_button = QPushButton()
        self.reload_db_button.setObjectName("SecondaryButton")
        self.reload_db_button.clicked.connect(self.reload_current_database)
        self.backup_db_button = QPushButton()
        self.backup_db_button.setObjectName("SecondaryButton")
        self.backup_db_button.clicked.connect(self.backup_current_database)
        current_button_row.addWidget(self.reload_db_button)
        current_button_row.addWidget(self.backup_db_button)
        self.reload_database_message = AlertMessage()
        self.reload_database_message.hide()
        current_button_row.addWidget(self.reload_database_message)
        current_button_row.addStretch()
        layout.addLayout(current_button_row)

        switch_form = QFormLayout()
        self.switch_database_title_label = self._section_label("")
        layout.addWidget(self.switch_database_title_label)

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
        switch_form.addRow(self.database_path_label, database_path_row)
        layout.addLayout(switch_form)

        switch_button_row = QHBoxLayout()
        self.apply_db_button = QPushButton()
        self.apply_db_button.setObjectName("SecondaryButton")
        self.apply_db_button.clicked.connect(self.apply_database_path)
        switch_button_row.addWidget(self.apply_db_button)
        self.switch_database_message = AlertMessage()
        self.switch_database_message.hide()
        switch_button_row.addWidget(self.switch_database_message)
        switch_button_row.addStretch()
        layout.addLayout(switch_button_row)

        new_form = QFormLayout()
        self.new_database_title_label = self._section_label("")
        layout.addWidget(self.new_database_title_label)
        self.new_database_path_edit = QLineEdit()
        self.new_database_browse_button = QPushButton()
        self.new_database_browse_button.clicked.connect(self.browse_new_database_path)
        new_database_path_row = QWidget()
        new_database_path_row.setObjectName("TransparentRow")
        new_database_path_layout = QHBoxLayout(new_database_path_row)
        new_database_path_layout.setContentsMargins(0, 0, 0, 0)
        new_database_path_layout.setSpacing(8)
        new_database_path_layout.addWidget(self.new_database_path_edit, 1)
        new_database_path_layout.addWidget(self.new_database_browse_button)
        self.new_database_path_label = QLabel()
        new_form.addRow(self.new_database_path_label, new_database_path_row)
        layout.addLayout(new_form)

        new_button_row = QHBoxLayout()
        self.create_db_button = QPushButton()
        self.create_db_button.setObjectName("SecondaryButton")
        self.create_db_button.clicked.connect(self.create_database_from_settings)
        new_button_row.addWidget(self.create_db_button)
        self.new_database_message = AlertMessage()
        self.new_database_message.hide()
        new_button_row.addWidget(self.new_database_message)
        new_button_row.addStretch()
        layout.addLayout(new_button_row)

        layout.addStretch()
        return panel

    def _build_about_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setSizePolicy(self.expanding_size_policy())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        self.about_settings_title_label = self._section_label("")
        layout.addWidget(self.about_settings_title_label)

        self.about_app_label = QLabel()
        self.about_app_value_label = QLabel("MindTask")
        self.about_version_label = QLabel()
        self.about_version_value_label = QLabel(__version__)
        self.about_author_value_label = QLabel()
        self.about_collaboration_value_label = QLabel()
        self.about_config_file_label = QLabel()
        self.about_config_file_value_label = QLabel(self.config_path)
        self.about_database_path_label = QLabel()
        self.about_database_path_value_label = QLabel(self.db.db_path)

        for value_label in (
            self.about_app_value_label,
            self.about_version_value_label,
            self.about_author_value_label,
            self.about_collaboration_value_label,
            self.about_config_file_value_label,
            self.about_database_path_value_label,
        ):
            value_label.setObjectName("MutedLabel")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setWordWrap(True)

        form.addRow(self.about_app_label, self.about_app_value_label)
        form.addRow(self.about_version_label, self.about_version_value_label)
        form.addRow(self.about_config_file_label, self.about_config_file_value_label)
        form.addRow(self.about_database_path_label, self.about_database_path_value_label)
        layout.addLayout(form)
        layout.addStretch()
        self.about_author_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.about_collaboration_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.about_author_value_label)
        layout.addWidget(self.about_collaboration_value_label)
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

    def show_inline_message(
        self,
        label: AlertMessage,
        message: str,
        severity: int = ALERT_INFO,
        timeout_ms: int = 3500,
    ) -> None:
        label.set_message(message, severity)
        if message:
            token = int(label.property("messageToken") or 0) + 1
            label.setProperty("messageToken", token)

            def hide_if_current() -> None:
                if int(label.property("messageToken") or 0) == token:
                    label.hide()

            QTimer.singleShot(timeout_ms, hide_if_current)

    def retranslate_settings_ui(self) -> None:
        self.settings_sections_label.setText(self.tr("settings"))
        self._retranslate_settings_sections()
        self.general_settings_title_label.setText(self.tr("settings_general"))
        self.data_settings_title_label.setText(self.tr("settings_data"))
        self.about_settings_title_label.setText(self.tr("settings_about"))
        self.about_app_label.setText(self.tr("application"))
        self.about_version_label.setText(self.tr("version"))
        self.about_author_value_label.setText(self.tr("designed_by", author=__author__))
        self.about_collaboration_value_label.setText(self.tr("coauthored_by_codex"))
        self.about_config_file_label.setText(self.tr("config_file"))
        self.about_database_path_label.setText(self.tr("database_path"))
        self.current_database_title_label.setText(self.tr("current_database"))
        self.current_database_path_label.setText(self.tr("database_path"))
        self.switch_database_title_label.setText(self.tr("switch_database"))
        self.new_database_title_label.setText(self.tr("new_database"))
        self.theme_label.setText(self.tr("theme"))
        self.language_label.setText(self.tr("language"))
        self.smart_task_sorting_label.setText(self.tr("smart_task_sorting"))
        self._update_smart_task_sorting_switch_text()
        self.smart_task_sorting_hint_label.setText(self.tr("smart_task_sorting_hint"))
        self.hide_completed_tasks_label.setText(self.tr("hide_completed_tasks"))
        self._update_hide_completed_tasks_switch_text()
        self.retranslate_shortcut_settings()
        self.database_path_label.setText(self.tr("database_path"))
        self.new_database_path_label.setText(self.tr("new_database_path"))
        self.apply_db_button.setText(self.tr("apply_database"))
        self.create_db_button.setText(self.tr("create_database"))
        self.reload_db_button.setText(self.tr("reload_current"))
        self.backup_db_button.setText(self.tr("backup_database"))
        self.database_browse_button.setText(self.tr("browse"))
        self.new_database_browse_button.setText(self.tr("browse"))
        self._retranslate_theme_combo()
        self._refresh_about_settings_info()
        self._refresh_data_settings_info()

    def _retranslate_theme_combo(self) -> None:
        current_theme = self.theme_combo.currentData()
        self.theme_combo.blockSignals(True)
        for index in range(self.theme_combo.count()):
            value = self.theme_combo.itemData(index)
            self.theme_combo.setItemText(index, self.tr(THEME_TRANSLATION_KEYS.get(value, "theme_system")))
        self.theme_combo.blockSignals(False)
        if isinstance(current_theme, str):
            self._set_theme_combo(current_theme)

    def _retranslate_settings_sections(self) -> None:
        current_row = max(0, self.settings_section_list.currentRow())
        labels = [
            self.tr("settings_general"),
            self.tr("settings_data"),
            self.tr("keyboard_shortcuts"),
            self.tr("settings_about"),
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

    def _update_smart_task_sorting_switch_text(self) -> None:
        key = "switch_on" if self.smart_task_sorting_checkbox.isChecked() else "switch_off"
        self.smart_task_sorting_checkbox.setText(self.tr(key))

    def _update_hide_completed_tasks_switch_text(self) -> None:
        key = "switch_on" if self.hide_completed_tasks_checkbox.isChecked() else "switch_off"
        self.hide_completed_tasks_checkbox.setText(self.tr(key))

    def apply_smart_task_sorting_from_checkbox(self, checked: bool) -> None:
        previous = self.smart_task_sorting
        self.smart_task_sorting = checked
        self._update_smart_task_sorting_switch_text()
        try:
            save_smart_task_sorting(checked, self.config_path)
        except Exception as exc:
            self.smart_task_sorting = previous
            self.smart_task_sorting_checkbox.blockSignals(True)
            self.smart_task_sorting_checkbox.setChecked(previous)
            self.smart_task_sorting_checkbox.blockSignals(False)
            self._update_smart_task_sorting_switch_text()
            QMessageBox.warning(
                self,
                self.tr("smart_task_sorting"),
                self.tr("could_not_save_smart_task_sorting", error=exc),
            )
            return
        self.refresh_tasks(force_detail=True)

    def apply_hide_completed_tasks_from_checkbox(self, checked: bool) -> None:
        previous = self.hide_completed_tasks
        self.hide_completed_tasks = checked
        self._update_hide_completed_tasks_switch_text()
        try:
            save_hide_completed_tasks(checked, self.config_path)
        except Exception as exc:
            self.hide_completed_tasks = previous
            self.hide_completed_tasks_checkbox.blockSignals(True)
            self.hide_completed_tasks_checkbox.setChecked(previous)
            self.hide_completed_tasks_checkbox.blockSignals(False)
            self._update_hide_completed_tasks_switch_text()
            QMessageBox.warning(
                self,
                self.tr("hide_completed_tasks"),
                self.tr("could_not_save_hide_completed_tasks", error=exc),
            )
            return
        self.refresh_tasks(force_detail=True)

    def apply_database_path(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            self.show_inline_message(
                self.switch_database_message,
                self.tr("database_path_required"),
                ALERT_DANGER,
            )
            return

        try:
            target_db = self._database_file_service().open_existing_database(database_path)
        except DatabasePathError as exc:
            self.show_inline_message(
                self.switch_database_message,
                self.tr(exc.key, **exc.kwargs),
                ALERT_DANGER,
            )
            return

        try:
            save_database_path(target_db.db_path, self.config_path)
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self._refresh_about_settings_info()
            self._refresh_data_settings_info()
            self.show_inline_message(self.switch_database_message, self.tr("database_updated"))
            self.show_status_message("status_database_switched", name=Path(self.db.db_path).name)
            self.refresh_all()
        except Exception as exc:
            self.show_inline_message(
                self.switch_database_message,
                self.tr("database_opened_config_failed", error=exc),
                ALERT_DANGER,
            )

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

    def browse_new_database_path(self) -> None:
        current = self.new_database_path_edit.text().strip() or str(Path(self.db.db_path).with_name("mindtask-new.db"))
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("create_new_database"),
            current,
            "SQLite (*.db *.sqlite *.sqlite3);;All files (*)",
        )
        if path:
            self.new_database_path_edit.setText(path)

    def create_database_from_settings(self) -> None:
        database_path = self.new_database_path_edit.text().strip()
        if not database_path:
            self.show_inline_message(
                self.new_database_message,
                self.tr("new_database_required"),
                ALERT_DANGER,
            )
            return

        try:
            target = self._database_file_service().inspect_new_database_target(database_path)
        except DatabasePathError as exc:
            self.show_inline_message(
                self.new_database_message,
                self.tr(exc.key, **exc.kwargs),
                ALERT_DANGER,
            )
            return

        confirm_message = (
            self.tr("overwrite_database_confirm", path=str(target.path))
            if target.exists
            else self.tr("create_database_confirm")
        )
        if not confirm_question(
            self,
            self.tr("create_database"),
            confirm_message,
            self.translator,
        ):
            return

        try:
            new_db = self._database_file_service().create_database(str(target.path), overwrite=target.exists)
            save_database_path(new_db.db_path, self.config_path)
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self.new_database_path_edit.clear()
            self._refresh_about_settings_info()
            self._refresh_data_settings_info()
            self.show_inline_message(self.new_database_message, self.tr("database_created"))
            self.show_status_message("status_database_created", name=Path(self.db.db_path).name)
            self.refresh_all()
        except DatabasePathError as exc:
            self.show_inline_message(
                self.new_database_message,
                self.tr(exc.key, **exc.kwargs),
                ALERT_DANGER,
            )
        except Exception as exc:
            self.show_inline_message(
                self.new_database_message,
                self.tr("could_not_create_database", error=exc),
                ALERT_DANGER,
            )

    def reload_current_database(self) -> None:
        try:
            self.db = MindTaskDB(config_path=self.config_path)
            self.database_path_edit.setText(self.db.db_path)
            self._refresh_about_settings_info()
            self._refresh_data_settings_info()
            self.show_inline_message(self.reload_database_message, self.tr("database_reloaded"))
            self.show_status_message("status_database_reloaded", name=Path(self.db.db_path).name)
            self.refresh_all()
        except Exception as exc:
            self.show_inline_message(
                self.reload_database_message,
                self.tr("could_not_reload_database", error=exc),
                ALERT_DANGER,
            )

    def backup_current_database(self) -> None:
        service = self._database_file_service()
        try:
            default_path = service.default_backup_path(self.db.db_path)
        except DatabasePathError as exc:
            self.show_inline_message(
                self.reload_database_message,
                self.tr(exc.key, **exc.kwargs),
                ALERT_DANGER,
            )
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("backup_database"),
            str(default_path),
            "SQLite (*.db *.sqlite *.sqlite3);;All files (*)",
        )
        if not target_path:
            return

        try:
            target = service.backup_database(self.db.db_path, target_path)
            self.show_inline_message(self.reload_database_message, self.tr("database_backup_created", path=str(target)))
            self.show_status_message("status_database_backed_up", name=target.name)
        except DatabasePathError as exc:
            self.show_inline_message(
                self.reload_database_message,
                self.tr(exc.key, **exc.kwargs),
                ALERT_DANGER,
            )

    def _database_file_service(self) -> DatabaseFileService:
        return DatabaseFileService(self.config_path, language=self.language)

    def _refresh_about_settings_info(self) -> None:
        if not hasattr(self, "about_config_file_value_label"):
            return
        self.about_version_value_label.setText(__version__)
        self.about_author_value_label.setText(self.tr("designed_by", author=__author__))
        self.about_config_file_value_label.setText(self.config_path)
        self.about_database_path_value_label.setText(self.db.db_path)

    def _refresh_data_settings_info(self) -> None:
        if not hasattr(self, "current_database_path_value_label"):
            return
        self.current_database_path_value_label.setText(self.db.db_path)
