"""Database selection flow for unavailable configured database files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QButtonGroup,
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
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.new_radio)
        self.mode_group.addButton(self.existing_radio)
        self.existing_radio.setChecked(True)

        self.database_path_edit = QLineEdit(str(Path(database_path)))
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_database_path)
        path_row = QHBoxLayout()
        path_row.addWidget(self.database_path_edit, 1)
        path_row.addWidget(self.browse_button)

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
        layout.addWidget(self.existing_radio)
        layout.addWidget(self.new_radio)
        layout.addLayout(path_row)
        layout.addLayout(button_row)

        self.retranslate()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr("database_unavailable_title"))
        self.title_label.setText(self.tr("database_unavailable_title"))
        self.intro_label.setText(self.tr("database_unavailable_intro"))
        message_key = "database_unavailable_invalid" if self.reason == "invalid" else "database_unavailable_missing"
        self.missing_message.set_message(
            self.tr(message_key, path=self.database_path),
            ALERT_DANGER,
        )
        self.existing_radio.setText(self.tr("use_existing_database"))
        self.new_radio.setText(self.tr("create_new_database"))
        self.browse_button.setText(self.tr("browse"))
        self.finish_button.setText(self.tr("finish"))
        self.cancel_button.setText(self.tr("cancel"))

    def browse_database_path(self) -> None:
        current = self.database_path_edit.text().strip() or self.database_path
        if self.existing_radio.isChecked():
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

    def finish_selection(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            key = "existing_database_required" if self.existing_radio.isChecked() else "new_database_required"
            QMessageBox.warning(self, self.tr("database"), self.tr(key))
            return

        service = DatabaseFileService(self.config_path, language=self.translator.language)
        try:
            if self.existing_radio.isChecked():
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
