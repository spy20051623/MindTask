"""First-run welcome and setup flow for the MindTask desktop UI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QButtonGroup,
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

from ..core import (
    create_config_from_template,
    get_default_database_path,
    get_local_config_path,
    get_user_config_path,
    save_database_path,
    save_ui_language,
)
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
        self.config_path = str(Path(config_path) if config_path else get_user_config_path())
        self.language = "en"
        self.translator = Translator(self.language)
        self._system_database_path = str(get_default_database_path())
        self._local_database_path = str(get_local_config_path().parent / "mindtask.db")

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
        self.config_location_title = QLabel()
        self.config_location_title.setObjectName("FieldLabel")
        self.system_config_radio = QRadioButton()
        self.local_config_radio = QRadioButton()
        self.config_location_group = QButtonGroup(self)
        self.config_location_group.addButton(self.system_config_radio)
        self.config_location_group.addButton(self.local_config_radio)
        self.system_config_radio.setChecked(True)
        self.system_config_radio.toggled.connect(self.change_config_location)
        self.database_mode_title = QLabel()
        self.database_mode_title.setObjectName("FieldLabel")

        self.existing_radio = QRadioButton()
        self.new_radio = QRadioButton()
        self.database_mode_group = QButtonGroup(self)
        self.database_mode_group.addButton(self.new_radio)
        self.database_mode_group.addButton(self.existing_radio)
        self.new_radio.setChecked(True)

        self.database_path_edit = QLineEdit(self._system_database_path)
        self.database_path_edit.setPlaceholderText(self._system_database_path)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_database_path)

        path_row = QHBoxLayout()
        path_row.addWidget(self.database_path_edit, 1)
        path_row.addWidget(self.browse_button)

        layout.addWidget(self.database_title)
        layout.addWidget(self.database_intro)
        layout.addWidget(self.config_location_title)
        layout.addWidget(self.system_config_radio)
        layout.addWidget(self.local_config_radio)
        layout.addSpacing(8)
        layout.addWidget(self.database_mode_title)
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
        self.config_location_title.setText(self.tr("config_location"))
        self.system_config_radio.setText(self.tr("system_config_recommended"))
        self.local_config_radio.setText(self.tr("local_config"))
        self.database_mode_title.setText(self.tr("database_mode"))
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
        current = self.database_path_edit.text().strip() or self._default_database_path()
        if self.existing_radio.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, self.tr("use_existing_database"), str(Path(current).parent), "SQLite (*.db *.sqlite *.sqlite3);;All files (*)")
        else:
            path, _ = QFileDialog.getSaveFileName(self, self.tr("create_new_database"), current, "SQLite (*.db *.sqlite *.sqlite3);;All files (*)")
        if path:
            self.database_path_edit.setText(path)

    def finish_setup(self) -> None:
        self.config_path = str(self._selected_config_path())
        database_path = self.database_path_edit.text().strip()
        if not database_path:
            key = "existing_database_required" if self.existing_radio.isChecked() else "new_database_required"
            QMessageBox.warning(self, self.tr("database"), self.tr(key))
            return

        try:
            Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
            if self.existing_radio.isChecked():
                existing_db = self._database_file_service().open_existing_database(database_path)
                target = Path(existing_db.db_path)
            else:
                target = self._database_file_service().inspect_new_database_target(database_path)
        except DatabasePathError as exc:
            QMessageBox.warning(self, self.tr("database"), self.tr(exc.key, **exc.kwargs))
            return
        except OSError as exc:
            QMessageBox.warning(self, self.tr("database"), str(exc))
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
            create_config_from_template(self.config_path)
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

    def change_config_location(self) -> None:
        old_default = self._local_database_path if self.system_config_radio.isChecked() else self._system_database_path
        new_default = self._default_database_path()
        current = self.database_path_edit.text().strip()
        if not current or current == old_default:
            self.database_path_edit.setText(new_default)
        self.database_path_edit.setPlaceholderText(new_default)

    def _selected_config_path(self) -> Path:
        return get_user_config_path() if self.system_config_radio.isChecked() else get_local_config_path()

    def _default_database_path(self) -> str:
        return self._system_database_path if self.system_config_radio.isChecked() else self._local_database_path
