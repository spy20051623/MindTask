"""Desktop dialogs used by the MindTask main window."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from .dialog_helpers import localize_dialog_buttons, required_label
from .i18n import Translator
from .style import THEME_SYSTEM, build_app_style


class ProjectDialog(QDialog):
    """Dialog for creating or renaming a project."""

    def __init__(self, name: str = "", language: str = "system", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.translator = Translator(language)
        self.setWindowTitle(self.tr("new_project"))
        theme = THEME_SYSTEM
        app = QApplication.instance()
        if app is not None:
            theme = app.property("mindtask_theme") or THEME_SYSTEM
        self.setStyleSheet(build_app_style(theme, app))

        self.name_edit = QLineEdit(name)

        form = QFormLayout(self)
        form.addRow(required_label(self.tr("name")), self.name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, self.translator)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def project_name(self) -> str:
        return self.name_edit.text().strip()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _accept_if_valid(self) -> None:
        if not self.project_name():
            QMessageBox.warning(self, self.tr("invalid_project"), self.tr("name_required"))
            return
        self.accept()
