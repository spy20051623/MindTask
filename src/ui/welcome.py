"""First-run welcome and setup flow for the MindTask desktop UI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import get_config_path, load_config, save_database_path, save_ui_language
from .settings.database_file_service import (
    DatabaseFileService,
    DatabasePathError,
)
from .shared.dialog_helpers import confirm_question
from .shared.i18n import LANGUAGE_LABELS, LANGUAGE_OPTIONS, Translator
from .shared.style import THEME_SYSTEM, build_app_style


class WelcomeDialog(QDialog):
    """Guided setup shown before the first desktop window opens."""

    def __init__(self, config_path: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_path = str(get_config_path(config_path))
        self.config = load_config(config_path)
        self.language = self.config.ui_language
        self.translator = Translator(self.language)

        self.setMinimumWidth(560)
        self.setWindowTitle(self.tr("welcome_title"))
        self.setStyleSheet(build_app_style(THEME_SYSTEM, None))

        self.stack = QStackedWidget()
        self.language_page = self._build_language_page()
        self.database_page = self._build_database_page()
        self.stack.addWidget(self.language_page)
        self.stack.addWidget(self.database_page)

        self.back_button = QPushButton()
        self.next_button = QPushButton()
        self.cancel_button = QPushButton()
        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(self.stack)
        layout.addLayout(buttons)

        self.retranslate()
        self.update_buttons()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _build_language_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("DetailPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.language_title = QLabel()
        self.language_title.setObjectName("SectionLabel")
        self.language_intro = QLabel()
        self.language_intro.setWordWrap(True)

        self.language_combo = QComboBox()
        for language in LANGUAGE_OPTIONS:
            self.language_combo.addItem(LANGUAGE_LABELS[language], language)
        index = self.language_combo.findData(self.language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        self.language_combo.currentIndexChanged.connect(self.change_language)

        layout.addWidget(self.language_title)
        layout.addWidget(self.language_intro)
        layout.addWidget(self.language_combo)
        layout.addStretch()
        return page

    def _build_database_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("DetailPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.database_title = QLabel()
        self.database_title.setObjectName("SectionLabel")
        self.database_intro = QLabel()
        self.database_intro.setWordWrap(True)

        self.existing_radio = QRadioButton()
        self.new_radio = QRadioButton()
        self.new_radio.setChecked(True)

        self.database_path_edit = QLineEdit(self.config.database_path)
        self.database_path_edit.setPlaceholderText("data/mindtask.db")
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_database_path)

        path_row = QHBoxLayout()
        path_row.addWidget(self.database_path_edit, 1)
        path_row.addWidget(self.browse_button)

        layout.addWidget(self.database_title)
        layout.addWidget(self.database_intro)
        layout.addWidget(self.new_radio)
        layout.addWidget(self.existing_radio)
        layout.addLayout(path_row)
        layout.addStretch()
        return page

    def change_language(self) -> None:
        language = self.language_combo.currentData()
        if not isinstance(language, str):
            return
        self.language = language
        self.translator.set_language(language)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr("welcome_title"))
        self.language_title.setText(self.tr("welcome_title"))
        self.language_intro.setText(self.tr("welcome_language_intro"))
        self.database_title.setText(self.tr("database"))
        self.database_intro.setText(self.tr("welcome_database_intro"))
        self.existing_radio.setText(self.tr("use_existing_database"))
        self.new_radio.setText(self.tr("create_new_database"))
        self.browse_button.setText(self.tr("browse"))
        self.back_button.setText(self.tr("back"))
        self.next_button.setText(self.tr("next") if self.stack.currentIndex() == 0 else self.tr("finish"))
        self.cancel_button.setText(self.tr("cancel"))

    def update_buttons(self) -> None:
        self.back_button.setEnabled(self.stack.currentIndex() > 0)
        self.next_button.setText(self.tr("next") if self.stack.currentIndex() == 0 else self.tr("finish"))

    def go_back(self) -> None:
        self.stack.setCurrentIndex(0)
        self.retranslate()
        self.update_buttons()

    def go_next(self) -> None:
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
            self.retranslate()
            self.update_buttons()
            return
        self.finish_setup()

    def browse_database_path(self) -> None:
        current = self.database_path_edit.text().strip() or self.config.database_path
        if self.existing_radio.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, self.tr("use_existing_database"), str(Path(current).parent), "SQLite (*.db *.sqlite *.sqlite3);;All files (*)")
        else:
            path, _ = QFileDialog.getSaveFileName(self, self.tr("create_new_database"), current, "SQLite (*.db *.sqlite *.sqlite3);;All files (*)")
        if path:
            self.database_path_edit.setText(path)

    def finish_setup(self) -> None:
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            key = "existing_database_required" if self.existing_radio.isChecked() else "new_database_required"
            QMessageBox.warning(self, self.tr("database"), self.tr(key))
            return

        try:
            if self.existing_radio.isChecked():
                existing_db = self._database_file_service().open_existing_database(database_path)
                target = Path(existing_db.db_path)
            else:
                target = self._database_file_service().inspect_new_database_target(database_path)
        except DatabasePathError as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr(exc.key, **exc.kwargs))
            return

        if self.new_radio.isChecked() and target.exists:
            if not confirm_question(
                self,
                self.tr("create_database"),
                self.tr("overwrite_database_confirm", path=str(target.path)),
                self.translator,
            ):
                return

        try:
            save_ui_language(self.language, self.config_path)
            if self.new_radio.isChecked():
                new_db = self._database_file_service().create_database(str(target.path), overwrite=target.exists)
                save_database_path(new_db.db_path, self.config_path)
            else:
                save_database_path(str(target), self.config_path)
        except DatabasePathError as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr(exc.key, **exc.kwargs))
            return
        except Exception as exc:
            QMessageBox.warning(self, self.tr("database"), str(exc))
            return

        self.accept()

    def _database_file_service(self) -> DatabaseFileService:
        return DatabaseFileService(self.config_path, language=self.language)
