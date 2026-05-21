"""Keyboard-only shortcut editor used by the desktop settings page."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLineEdit


SHIFTED_KEY_ALIASES = {
    Qt.Key.Key_Exclam: Qt.Key.Key_1,
    Qt.Key.Key_At: Qt.Key.Key_2,
    Qt.Key.Key_NumberSign: Qt.Key.Key_3,
    Qt.Key.Key_Dollar: Qt.Key.Key_4,
    Qt.Key.Key_Percent: Qt.Key.Key_5,
    Qt.Key.Key_AsciiCircum: Qt.Key.Key_6,
    Qt.Key.Key_Ampersand: Qt.Key.Key_7,
    Qt.Key.Key_Asterisk: Qt.Key.Key_8,
    Qt.Key.Key_ParenLeft: Qt.Key.Key_9,
    Qt.Key.Key_ParenRight: Qt.Key.Key_0,
    Qt.Key.Key_Underscore: Qt.Key.Key_Minus,
    Qt.Key.Key_Plus: Qt.Key.Key_Equal,
    Qt.Key.Key_BraceLeft: Qt.Key.Key_BracketLeft,
    Qt.Key.Key_BraceRight: Qt.Key.Key_BracketRight,
    Qt.Key.Key_Bar: Qt.Key.Key_Backslash,
    Qt.Key.Key_Colon: Qt.Key.Key_Semicolon,
    Qt.Key.Key_QuoteDbl: Qt.Key.Key_Apostrophe,
    Qt.Key.Key_Less: Qt.Key.Key_Comma,
    Qt.Key.Key_Greater: Qt.Key.Key_Period,
    Qt.Key.Key_Question: Qt.Key.Key_Slash,
    Qt.Key.Key_AsciiTilde: Qt.Key.Key_QuoteLeft,
}


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
        self._sequence = self._normalized_sequence(sequence)
        self.setText(self._sequence.toString(QKeySequence.SequenceFormat.NativeText))
        self.keySequenceChanged.emit(self._sequence)

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
        if key == Qt.Key.Key_Return:
            key = Qt.Key.Key_Enter
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            key = SHIFTED_KEY_ALIASES.get(key, key)
        if key == Qt.Key.Key_Backspace and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.setKeySequence(QKeySequence())
            event.accept()
            return
        sequence_text = self._sequence_text_from_event(key, event.modifiers())
        self.setKeySequence(QKeySequence(sequence_text))
        event.accept()

    def _sequence_text_from_event(self, key: int, modifiers: Qt.KeyboardModifier) -> str:
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Meta")
        parts.append(QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText))
        return "+".join(part for part in parts if part)

    def _normalized_sequence(self, sequence: QKeySequence) -> QKeySequence:
        portable_text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        parts = portable_text.split("+")
        if parts and parts[-1] == "Return":
            return QKeySequence("+".join([*parts[:-1], "Enter"]))
        return sequence

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
