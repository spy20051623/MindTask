"""Database settings panel and commands."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core import MindTaskDB, save_database_path
from ..shared.alert_message import ALERT_DANGER, AlertMessage
from ..shared.dialog_helpers import confirm_question
from .database_file_service import DatabaseFileService, DatabasePathError


class DatabaseSettingsMixin:
    """Mixin for database settings UI and database file workflows."""

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

    def retranslate_database_settings(self) -> None:
        self.data_settings_title_label.setText(self.tr("settings_data"))
        self.current_database_title_label.setText(self.tr("current_database"))
        self.current_database_path_label.setText(self.tr("database_path"))
        self.switch_database_title_label.setText(self.tr("switch_database"))
        self.new_database_title_label.setText(self.tr("new_database"))
        self.database_path_label.setText(self.tr("database_path"))
        self.new_database_path_label.setText(self.tr("new_database_path"))
        self.apply_db_button.setText(self.tr("apply_database"))
        self.create_db_button.setText(self.tr("create_database"))
        self.reload_db_button.setText(self.tr("reload_current"))
        self.backup_db_button.setText(self.tr("backup_database"))
        self.database_browse_button.setText(self.tr("browse"))
        self.new_database_browse_button.setText(self.tr("browse"))
        self._refresh_data_settings_info()

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

    def _refresh_data_settings_info(self) -> None:
        if not hasattr(self, "current_database_path_value_label"):
            return
        self.current_database_path_value_label.setText(self.db.db_path)
