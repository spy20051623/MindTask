"""Keyboard-only shortcut editor used by the desktop settings page."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLineEdit


class ShortcutKeySequenceEdit(QLineEdit):
    """Read-only field that records keyboard shortcuts without mouse input."""

    keySequenceChanged = Signal(QKeySequence)
    focus_changed = Signal(bool)

    def __init__(self, sequence: QKeySequence):
        super().__init__()
        self._sequence = QKeySequence()
        self.setReadOnly(True)
        self.setKeySequence(sequence)

    def keySequence(self) -> QKeySequence:
        return self._sequence

    def setKeySequence(self, sequence: QKeySequence) -> None:
        self._sequence = sequence
        self.setText(sequence.toString(QKeySequence.SequenceFormat.NativeText))
        self.keySequenceChanged.emit(sequence)

    def focusInEvent(self, event: Any) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event: Any) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        if key in {
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
        }:
            event.accept()
            return
        if key == Qt.Key.Key_Backspace and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.setKeySequence(QKeySequence())
            event.accept()
            return
        modifiers = event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        self.setKeySequence(QKeySequence(modifiers.value | key))
        event.accept()

    def mousePressEvent(self, event: Any) -> None:
        self._accept_mouse_event(event)

    def mouseMoveEvent(self, event: Any) -> None:
        event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:
        event.accept()

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self._accept_mouse_event(event)

    def _accept_mouse_event(self, event: QEvent) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        event.accept()
