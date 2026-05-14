"""Small helpers shared by desktop dialogs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QMessageBox, QWidget

from .i18n import Translator


def required_label(text: str) -> QLabel:
    label = QLabel(f'{text} <span style="color:#dc2626;">*</span>')
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


def localize_dialog_buttons(buttons: QDialogButtonBox, translator: Translator) -> None:
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    if ok_button is not None:
        ok_button.setText(translator.text("ok"))
    if cancel_button is not None:
        cancel_button.setText(translator.text("cancel"))


def confirm_question(parent: QWidget, title: str, message: str, translator: Translator) -> bool:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Question)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    yes_button = dialog.addButton(translator.text("yes"), QMessageBox.ButtonRole.YesRole)
    no_button = dialog.addButton(translator.text("no"), QMessageBox.ButtonRole.NoRole)
    dialog.setDefaultButton(no_button)
    dialog.exec()
    return dialog.clickedButton() == yes_button
