"""Task-detail checklist widgets backed by Markdown details text."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QWidget

from .checklist_markdown import (
    CHECKLIST_ITEM_TEXT,
    ChecklistMarkdown,
)
from ..shared.dialog_helpers import confirm_question


class ChecklistItemLabel(QLabel):
    """Label that enters inline checklist editing on double click."""

    def __init__(self, text: str, handler: Any, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._handler = handler

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self._handler()
        super().mouseDoubleClickEvent(event)


class ChecklistItemEdit(QLineEdit):
    """Inline checklist editor with Enter-save, focus-save, and Esc-cancel behavior."""

    def __init__(self, text: str, save_handler: Any, cancel_handler: Any, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._save_handler = save_handler
        self._cancel_handler = cancel_handler
        self._finished = False

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finished = True
            self._save_handler(self.text())
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._finished = True
            self._cancel_handler()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: Any) -> None:
        if not self._finished:
            self._finished = True
            self._save_handler(self.text())
        super().focusOutEvent(event)


class ChecklistPanelMixin:
    """Mixin for rendering and editing Markdown-backed checklist items."""

    def refresh_checklist_from_description(self) -> None:
        if not hasattr(self, "checklist_items_layout"):
            return
        while self.checklist_items_layout.count():
            item = self.checklist_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        items = ChecklistMarkdown(self.description_edit.toPlainText()).items()
        completed = sum(1 for item in items if item.completed)
        total = len(items)
        self.checklist_progress_label.setText(self.tr("checklist_progress", completed=completed, total=total))
        self.checklist_empty_label.setVisible(total == 0)
        self.checklist_items_widget.setVisible(total > 0)

        for checklist_item in items:
            row = QWidget()
            row.setObjectName("TransparentRow")
            row.setProperty("lineIndex", checklist_item.line_index)
            row.setProperty("itemText", checklist_item.text)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            done_button = QPushButton()
            done_button.setCheckable(True)
            done_button.setChecked(checklist_item.completed)
            done_button.setAccessibleName(self.tr("toggle_checklist_item"))
            done_button.setObjectName("ChecklistDoneButton")
            done_button.setFixedSize(24, 24)
            done_button.setIconSize(QSize(14, 14))
            self._set_checklist_done_button_icon(done_button)
            done_button.clicked.connect(
                lambda _checked=False, line_index=checklist_item.line_index, text=checklist_item.text: (
                    self.toggle_checklist_item_in_description(line_index, text)
                )
            )

            label = ChecklistItemLabel(
                checklist_item.text or self.tr("untitled_checklist_item"),
                lambda line_index=checklist_item.line_index, text=checklist_item.text: (
                    self.edit_checklist_item_text(line_index, text)
                ),
            )
            label.setObjectName("ChecklistItemLabel")
            label.setToolTip(self.tr("edit_checklist_item"))

            delete_button = self._icon_button(
                self.tr("delete_checklist_item"),
                "fa6s.minus",
                "-",
                lambda line_index=checklist_item.line_index, text=checklist_item.text: (
                    self.delete_checklist_item_from_description(line_index, text)
                ),
            )
            delete_button.setFixedSize(28, 28)
            delete_button.setIconSize(QSize(15, 15))

            row_layout.addWidget(done_button)
            row_layout.addWidget(label, 1)
            row_layout.addWidget(delete_button)
            self.checklist_items_layout.addWidget(row)

    def toggle_checklist_item_in_description(self, line_index: int, expected_text: str) -> None:
        updated = ChecklistMarkdown(self.description_edit.toPlainText()).toggle_line(line_index, expected_text)
        if updated == self.description_edit.toPlainText():
            QMessageBox.information(self, self.tr("checklist"), self.tr("checklist_item_mismatch"))
            self.refresh_checklist_from_description()
            return
        self._set_description_draft(updated)

    def edit_checklist_item_text(self, line_index: int, expected_text: str) -> None:
        if not self._checklist_line_matches(line_index, expected_text):
            QMessageBox.information(self, self.tr("checklist"), self.tr("checklist_item_mismatch"))
            self.refresh_checklist_from_description()
            return
        row = self._checklist_row_widget(line_index, expected_text)
        if row is None:
            self.refresh_checklist_from_description()
            return
        layout = row.layout()
        if layout is None:
            return
        old_label_item = layout.itemAt(1)
        old_label = old_label_item.widget() if old_label_item is not None else None
        if old_label is not None:
            old_label.hide()
        editor = ChecklistItemEdit(
            expected_text,
            lambda new_text, line_index=line_index, expected_text=expected_text: (
                self.save_checklist_item_text(line_index, expected_text, new_text)
            ),
            self.refresh_checklist_from_description,
        )
        editor.setObjectName("ChecklistInlineEditor")
        layout.insertWidget(1, editor, 1)
        editor.setFocus(Qt.FocusReason.MouseFocusReason)
        editor.selectAll()

    def save_checklist_item_text(self, line_index: int, expected_text: str, new_text: str) -> None:
        updated = ChecklistMarkdown(self.description_edit.toPlainText()).update_text(line_index, expected_text, new_text)
        if updated == self.description_edit.toPlainText():
            if not self._checklist_line_matches(line_index, expected_text):
                QMessageBox.information(self, self.tr("checklist"), self.tr("checklist_item_mismatch"))
            self.refresh_checklist_from_description()
            return
        self._set_description_draft(updated)

    def _checklist_row_widget(self, line_index: int, expected_text: str) -> Optional[QWidget]:
        for index in range(self.checklist_items_layout.count()):
            item = self.checklist_items_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if (
                widget is not None
                and widget.property("lineIndex") == line_index
                and widget.property("itemText") == expected_text
            ):
                return widget
        return None

    def _checklist_line_matches(self, line_index: int, expected_text: str) -> bool:
        items = ChecklistMarkdown(self.description_edit.toPlainText()).items()
        return any(item.line_index == line_index and item.text == expected_text for item in items)

    def delete_checklist_item_from_description(self, line_index: int, expected_text: str) -> None:
        if not confirm_question(
            self,
            self.tr("delete_checklist_item"),
            self.tr("delete_checklist_item_confirm", item=expected_text or self.tr("untitled_checklist_item")),
            self.translator,
        ):
            return
        updated = ChecklistMarkdown(self.description_edit.toPlainText()).delete_line(line_index, expected_text)
        if updated == self.description_edit.toPlainText():
            QMessageBox.information(self, self.tr("checklist"), self.tr("checklist_item_mismatch"))
            self.refresh_checklist_from_description()
            return
        self._set_description_draft(updated)

    def add_checklist_item_to_description(self) -> None:
        updated, line_index = ChecklistMarkdown(self.description_edit.toPlainText()).append_item(CHECKLIST_ITEM_TEXT)
        self._set_description_draft(updated)
        self.edit_checklist_item_text(line_index, CHECKLIST_ITEM_TEXT)
