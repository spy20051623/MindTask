"""Shortcut settings panel and handlers."""

from __future__ import annotations

from typing import Dict

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..core import DEFAULT_UI_SHORTCUTS, save_ui_shortcuts
from .shortcut_editor import ShortcutKeySequenceEdit


SHORTCUT_ACTIONS = (
    ("open_tasks", "shortcut_open_tasks"),
    ("open_projects", "shortcut_open_projects"),
    ("open_settings", "shortcut_open_settings"),
    ("new_task", "shortcut_new_task_label"),
    ("focus_search", "shortcut_focus_search"),
    ("escape_tasks", "shortcut_escape_tasks"),
    ("refresh", "shortcut_refresh"),
    ("undo", "shortcut_undo"),
    ("history", "shortcut_history"),
    ("save_task", "shortcut_save_task"),
    ("complete_task", "shortcut_complete_task"),
    ("delete_task", "shortcut_delete_task"),
)


class ShortcutSettingsMixin:
    """Mixin for shortcut settings UI and persistence."""

    def _build_shortcut_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setSizePolicy(self.expanding_size_policy())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        self.shortcuts_title_label = self._section_label("")
        layout.addWidget(self.shortcuts_title_label)
        self.shortcut_labels: Dict[str, QLabel] = {}
        self.shortcut_edits: Dict[str, ShortcutKeySequenceEdit] = {}
        self.shortcut_rows: Dict[str, QFrame] = {}
        self.shortcut_active_rows: set[str] = set()
        self.shortcut_cancel_buttons: Dict[str, QPushButton] = {}
        self.shortcut_default_buttons: Dict[str, QPushButton] = {}
        for action, _translation_key in SHORTCUT_ACTIONS:
            label = QLabel()
            row = QFrame()
            row.setObjectName("ShortcutRow")
            row.setProperty("shortcutModified", False)
            row.setProperty("shortcutActive", False)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)
            edit = ShortcutKeySequenceEdit(QKeySequence(self.shortcut_sequences.get(action, "")))
            edit.keySequenceChanged.connect(
                lambda _sequence, current_action=action: self.update_shortcut_row_state(current_action)
            )
            edit.editingFinished.connect(lambda current_action=action: self.update_shortcut_row_state(current_action))
            edit.focus_changed.connect(
                lambda has_focus, current_action=action: self.update_shortcut_focus_state(current_action, has_focus)
            )
            cancel_button = QPushButton()
            cancel_button.setObjectName("SecondaryButton")
            cancel_button.clicked.connect(
                lambda _checked=False, current_action=action: self.cancel_shortcut_change(current_action)
            )
            default_button = QPushButton()
            default_button.setObjectName("SecondaryButton")
            default_button.clicked.connect(
                lambda _checked=False, current_action=action: self.reset_shortcut_to_default(current_action)
            )
            row_layout.addWidget(edit, 1)
            row_layout.addWidget(cancel_button)
            row_layout.addWidget(default_button)
            self.shortcut_labels[action] = label
            self.shortcut_edits[action] = edit
            self.shortcut_rows[action] = row
            self.shortcut_cancel_buttons[action] = cancel_button
            self.shortcut_default_buttons[action] = default_button
            form.addRow(label, row)
        layout.addLayout(form)

        shortcut_button_row = QWidget()
        shortcut_button_row.setObjectName("TransparentRow")
        shortcut_button_layout = QHBoxLayout(shortcut_button_row)
        shortcut_button_layout.setContentsMargins(0, 0, 0, 0)
        shortcut_button_layout.setSpacing(8)
        self.apply_shortcuts_button = QPushButton()
        self.apply_shortcuts_button.clicked.connect(self.apply_shortcuts_from_settings)
        self.reset_shortcuts_button = QPushButton()
        self.reset_shortcuts_button.setObjectName("SecondaryButton")
        self.reset_shortcuts_button.clicked.connect(self.reset_all_shortcuts_to_defaults)
        shortcut_button_layout.addWidget(self.apply_shortcuts_button)
        shortcut_button_layout.addWidget(self.reset_shortcuts_button)
        self.shortcuts_message = QLabel("")
        self.shortcuts_message.setObjectName("MutedLabel")
        self.shortcuts_message.hide()
        shortcut_button_layout.addWidget(self.shortcuts_message)
        shortcut_button_layout.addStretch()
        layout.addWidget(shortcut_button_row)
        layout.addStretch()
        return panel

    def retranslate_shortcut_settings(self) -> None:
        self.shortcuts_title_label.setText(self.tr("keyboard_shortcuts"))
        for action, translation_key in SHORTCUT_ACTIONS:
            self.shortcut_labels[action].setText(self.tr(translation_key))
            self.shortcut_cancel_buttons[action].setText(self.tr("cancel_change"))
            self.shortcut_default_buttons[action].setText(self.tr("restore_default"))
            self.update_shortcut_row_state(action)
        self.apply_shortcuts_button.setText(self.tr("apply_shortcuts"))
        self.reset_shortcuts_button.setText(self.tr("reset_all_shortcuts"))

    def apply_shortcuts_from_settings(self) -> None:
        shortcuts = self._shortcut_settings_sequences()
        duplicate = self._first_duplicate_shortcut(shortcuts)
        if duplicate:
            QMessageBox.warning(
                self,
                self.tr("keyboard_shortcuts"),
                self.tr("duplicate_shortcut", shortcut=duplicate),
            )
            return
        try:
            save_ui_shortcuts(shortcuts, self.config_path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("keyboard_shortcuts"), self.tr("could_not_save_shortcuts", error=exc))
            return
        self.shortcut_sequences = shortcuts
        self._build_shortcuts()
        self.update_shortcut_change_indicators()
        self.show_inline_message(self.shortcuts_message, self.tr("shortcuts_updated"))

    def cancel_shortcut_change(self, action: str) -> None:
        self.shortcut_edits[action].setKeySequence(QKeySequence(self.shortcut_sequences.get(action, "")))
        self.update_shortcut_row_state(action)

    def reset_shortcut_to_default(self, action: str) -> None:
        self.shortcut_edits[action].setKeySequence(QKeySequence(DEFAULT_UI_SHORTCUTS.get(action, "")))
        self.update_shortcut_row_state(action)

    def reset_all_shortcuts_to_defaults(self) -> None:
        for action, sequence in DEFAULT_UI_SHORTCUTS.items():
            self.shortcut_edits[action].setKeySequence(QKeySequence(sequence))
            self.update_shortcut_row_state(action)

    def update_shortcut_change_indicators(self) -> None:
        for action, _translation_key in SHORTCUT_ACTIONS:
            self.update_shortcut_row_state(action)

    def update_shortcut_row_state(self, action: str) -> None:
        is_modified = self._shortcut_edit_text(action) != self._saved_shortcut_text(action)
        self.shortcut_cancel_buttons[action].setEnabled(is_modified)
        self._set_shortcut_row_property(action, "shortcutModified", is_modified)

    def update_shortcut_focus_state(self, action: str, has_focus: bool) -> None:
        if has_focus:
            self.shortcut_active_rows.add(action)
        else:
            self.shortcut_active_rows.discard(action)
        self._set_shortcut_row_property(action, "shortcutActive", has_focus)

    def _set_shortcut_row_property(self, action: str, name: str, value: bool) -> None:
        row = self.shortcut_rows[action]
        row.setProperty(name, value)
        row.style().unpolish(row)
        row.style().polish(row)
        row.update()

    def _shortcut_edit_text(self, action: str) -> str:
        return self.shortcut_edits[action].keySequence().toString(QKeySequence.SequenceFormat.PortableText)

    def _saved_shortcut_text(self, action: str) -> str:
        return QKeySequence(self.shortcut_sequences.get(action, "")).toString(QKeySequence.SequenceFormat.PortableText)

    def _shortcut_settings_sequences(self) -> Dict[str, str]:
        shortcuts: Dict[str, str] = {}
        for action, _translation_key in SHORTCUT_ACTIONS:
            shortcuts[action] = self._shortcut_edit_text(action)
        return shortcuts

    def _first_duplicate_shortcut(self, shortcuts: Dict[str, str]) -> str:
        seen = set()
        for sequence in shortcuts.values():
            key_sequence = QKeySequence(sequence)
            if key_sequence.isEmpty():
                continue
            canonical = key_sequence.toString(QKeySequence.SequenceFormat.PortableText)
            if canonical in seen:
                return canonical
            seen.add(canonical)
        return ""
