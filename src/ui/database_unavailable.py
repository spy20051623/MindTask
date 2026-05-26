"""Database selection flow for unavailable configured database files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..core import save_database_path
from ..core.migrations import available_migration_start_versions, migration_start_version
from .settings.database_file_service import DatabaseFileService, DatabasePathError
from .shared.alert_message import ALERT_DANGER, AlertMessage
from .shared.dialog_helpers import confirm_question
from .shared.i18n import Translator
from .shared.style import THEME_SYSTEM, build_app_style


class DatabaseUnavailableDialog(QDialog):
    """Let users choose how to continue when the configured database cannot open."""

    def __init__(
        self,
        config_path: str,
        database_path: str,
        language: str = "en",
        reason: str = "missing",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.config_path = config_path
        self.database_path = database_path
        self.reason = reason
        self.translator = Translator(language)

        self.setMinimumWidth(600)
        self.setWindowTitle(self.tr("database_unavailable_title"))
        self.setStyleSheet(build_app_style(THEME_SYSTEM, None))

        self.title_label = QLabel()
        self.title_label.setObjectName("SectionLabel")
        self.intro_label = QLabel()
        self.intro_label.setWordWrap(True)
        self.missing_message = AlertMessage()

        self.new_radio = QRadioButton()
        self.existing_radio = QRadioButton()
        self.migrate_radio = QRadioButton()
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.new_radio)
        self.mode_group.addButton(self.existing_radio)
        self.mode_group.addButton(self.migrate_radio)
        self.mode_group.buttonClicked.connect(self.update_migration_version_visibility)
        if self.reason == "migration":
            self.migrate_radio.setChecked(True)
        else:
            self.existing_radio.setChecked(True)

        self.database_path_edit = QLineEdit(str(Path(database_path)))
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_database_path)
        path_row = QHBoxLayout()
        path_row.addWidget(self.database_path_edit, 1)
        path_row.addWidget(self.browse_button)

        self.version_label = QLabel()
        self.version_combo = QComboBox()
        version_row = QHBoxLayout()
        version_row.addWidget(self.version_label)
        version_row.addWidget(self.version_combo, 1)

        self.finish_button = QPushButton()
        self.cancel_button = QPushButton()
        self.finish_button.clicked.connect(self.finish_selection)
        self.cancel_button.clicked.connect(self.reject)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.finish_button)
        button_row.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.missing_message)
        layout.addSpacing(6)
        layout.addWidget(self.migrate_radio)
        layout.addLayout(version_row)
        layout.addWidget(self.existing_radio)
        layout.addWidget(self.new_radio)
        layout.addLayout(path_row)
        layout.addLayout(button_row)

        self.retranslate()
        self.refresh_migration_version()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr("database_unavailable_title"))
        self.title_label.setText(self.tr("database_unavailable_title"))
        self.intro_label.setText(self.tr("database_unavailable_intro"))
        if self.reason == "migration":
            message_key = "database_unavailable_migration_required"
        elif self.reason == "invalid":
            message_key = "database_unavailable_invalid"
        else:
            message_key = "database_unavailable_missing"
        self.missing_message.set_message(
            self.tr(message_key, path=self.database_path),
            ALERT_DANGER,
        )
        self.existing_radio.setText(self.tr("use_existing_database"))
        self.migrate_radio.setText(self.tr("migrate_database"))
        self.migrate_radio.setVisible(self.reason == "migration")
        self.version_label.setText(self.tr("current_database_version"))
        self.populate_migration_versions()
        self.new_radio.setText(self.tr("create_new_database"))
        self.browse_button.setText(self.tr("browse"))
        self.finish_button.setText(self.tr("finish"))
        self.cancel_button.setText(self.tr("cancel"))
        self.update_migration_version_visibility()

    def update_migration_version_visibility(self) -> None:
        visible = self.reason == "migration" and self.migrate_radio.isChecked()
        self.version_label.setVisible(visible)
        self.version_combo.setVisible(visible)

    def populate_migration_versions(self) -> None:
        current = self.version_combo.currentData()
        versions = available_migration_start_versions()
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for version in versions:
            self.version_combo.addItem(self.display_migration_version(version), version)
        if current in versions:
            self.select_migration_version(current)
        self.version_combo.blockSignals(False)

    def refresh_migration_version(self) -> None:
        if self.reason != "migration":
            self.update_migration_version_visibility()
            return
        service = DatabaseFileService(self.config_path, language=self.translator.language)
        try:
            inspected = service.inspect_existing_database(self.database_path_edit.text().strip())
            self.select_migration_version(migration_start_version(inspected.stored_version))
        except Exception:
            self.select_migration_version(None)
        self.update_migration_version_visibility()

    def display_migration_version(self, version: Optional[str]) -> str:
        if version is None:
            return self.tr("migration_version_legacy")
        return str(version).strip()

    def select_migration_version(self, version: Optional[str]) -> None:
        for index in range(self.version_combo.count()):
            if self.version_combo.itemData(index) == version:
                self.version_combo.setCurrentIndex(index)
                return
        if self.version_combo.count():
            self.version_combo.setCurrentIndex(0)

    def selected_migration_start_version(self) -> Optional[str]:
        return self.version_combo.currentData()

    def browse_database_path(self) -> None:
        current = self.database_path_edit.text().strip() or self.database_path
        if self.existing_radio.isChecked() or self.migrate_radio.isChecked():
            path, _ = QFileDialog.getOpenFileName(
                self,
                self.tr("use_existing_database"),
                str(Path(current).parent),
                "SQLite (*.db *.sqlite *.sqlite3);;All files (*)",
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self,
                self.tr("create_new_database"),
                current,
                "SQLite (*.db *.sqlite *.sqlite3);;All files (*)",
            )
        if path:
            self.database_path_edit.setText(path)
            self.refresh_migration_version()

    def finish_selection(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            key = "existing_database_required" if not self.new_radio.isChecked() else "new_database_required"
            QMessageBox.warning(self, self.tr("database"), self.tr(key))
            return

        service = DatabaseFileService(self.config_path, language=self.translator.language)
        try:
            if self.migrate_radio.isChecked():
                migrated = service.migrate_database(
                    database_path,
                    migration_start_version=self.selected_migration_start_version(),
                )
                save_database_path(migrated.db.db_path, self.config_path)
                QMessageBox.information(
                    self,
                    self.tr("migrate_database"),
                    self.tr("database_migrated_with_backup", path=str(migrated.backup_path)),
                )
            elif self.existing_radio.isChecked():
                selected_db = service.open_existing_database(database_path)
                save_database_path(selected_db.db_path, self.config_path)
            else:
                target = service.inspect_new_database_target(database_path)
                if target.exists and not confirm_question(
                    self,
                    self.tr("create_database"),
                    self.tr("overwrite_database_confirm", path=str(target.path)),
                    self.translator,
                ):
                    return
                new_db = service.create_database(str(target.path), overwrite=target.exists)
                save_database_path(new_db.db_path, self.config_path)
        except DatabasePathError as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr(exc.key, **exc.kwargs))
            return
        except Exception as exc:
            QMessageBox.warning(self, self.tr("database"), str(exc))
            return

        self.accept()
