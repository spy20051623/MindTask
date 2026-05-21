"""Shortcut settings panel and handlers."""

from __future__ import annotations

from typing import Dict

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ...core import DEFAULT_UI_SHORTCUTS, save_ui_shortcuts
from ..shared.alert_message import ALERT_DANGER, AlertMessage
from .shortcut_editor import ShortcutKeySequenceEdit


SHORTCUT_ACTIONS = (
    ("open_tasks", "shortcut_open_tasks"),
    ("open_settings", "shortcut_open_settings"),
    ("open_projects", "shortcut_open_projects"),
    ("new_task", "shortcut_new_task_label"),
    ("focus_search", "shortcut_focus_search"),
    ("escape_tasks", "shortcut_escape_tasks"),
    ("refresh", "shortcut_refresh"),
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
            row.setProperty("shortcutDuplicate", False)
            row.setProperty("shortcutInvalid", False)
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
        self.shortcuts_message = AlertMessage()
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
        invalid = self._first_invalid_shortcut(shortcuts)
        if invalid:
            self.update_shortcut_change_indicators()
            self.show_inline_message(self.shortcuts_message, self.tr("invalid_shortcut", shortcut=invalid), ALERT_DANGER)
            return
        duplicate = self._first_duplicate_shortcut(shortcuts)
        if duplicate:
            self.update_shortcut_change_indicators()
            self.show_inline_message(
                self.shortcuts_message,
                self.tr("duplicate_shortcut", shortcut=duplicate),
                ALERT_DANGER,
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
        self.show_status_message("status_shortcuts_saved")

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
        self._update_shortcut_warning_rows()
        for action, _translation_key in SHORTCUT_ACTIONS:
            self.update_shortcut_row_state(action)

    def update_shortcut_row_state(self, action: str) -> None:
        is_modified = self._shortcut_edit_text(action) != self._saved_shortcut_text(action)
        self.shortcut_cancel_buttons[action].setEnabled(is_modified)
        self._set_shortcut_row_property(action, "shortcutModified", is_modified)
        self._update_shortcut_warning_rows()

    def update_shortcut_focus_state(self, action: str, has_focus: bool) -> None:
        if has_focus:
            self.shortcut_active_rows.add(action)
        else:
            self.shortcut_active_rows.discard(action)
        self._set_shortcut_row_property(action, "shortcutActive", has_focus)
        self._set_window_shortcuts_enabled(not self.shortcut_active_rows)

    def _set_window_shortcuts_enabled(self, enabled: bool) -> None:
        for shortcut in getattr(self, "shortcuts", []):
            shortcut.setEnabled(enabled)

    def _update_shortcut_warning_rows(self) -> None:
        shortcuts = self._shortcut_settings_sequences()
        invalids = self._invalid_shortcut_actions(shortcuts)
        duplicates = self._duplicate_shortcut_actions(shortcuts)
        for action, _translation_key in SHORTCUT_ACTIONS:
            self._set_shortcut_row_property(action, "shortcutInvalid", action in invalids)
            self._set_shortcut_row_property(action, "shortcutDuplicate", action in duplicates)

    def _update_duplicate_shortcut_rows(self) -> None:
        duplicates = self._duplicate_shortcut_actions(self._shortcut_settings_sequences())
        for action, _translation_key in SHORTCUT_ACTIONS:
            self._set_shortcut_row_property(action, "shortcutDuplicate", action in duplicates)

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
            canonical = self._canonical_shortcut_text(sequence)
            if not canonical:
                continue
            if canonical in seen:
                return canonical
            seen.add(canonical)
        return ""

    def _first_invalid_shortcut(self, shortcuts: Dict[str, str]) -> str:
        for sequence in shortcuts.values():
            canonical = self._canonical_shortcut_text(sequence)
            if canonical and not self._is_allowed_shortcut(canonical):
                return canonical
        return ""

    def _invalid_shortcut_actions(self, shortcuts: Dict[str, str]) -> set[str]:
        invalids = set()
        for action, sequence in shortcuts.items():
            canonical = self._canonical_shortcut_text(sequence)
            if canonical and not self._is_allowed_shortcut(canonical):
                invalids.add(action)
        return invalids

    def _duplicate_shortcut_actions(self, shortcuts: Dict[str, str]) -> set[str]:
        by_sequence: Dict[str, list[str]] = {}
        for action, sequence in shortcuts.items():
            canonical = self._canonical_shortcut_text(sequence)
            if not canonical:
                continue
            by_sequence.setdefault(canonical, []).append(action)
        return {
            action
            for actions in by_sequence.values()
            if len(actions) > 1
            for action in actions
        }

    def _canonical_shortcut_text(self, sequence: str) -> str:
        key_sequence = QKeySequence(sequence)
        if key_sequence.isEmpty():
            return ""
        canonical = key_sequence.toString(QKeySequence.SequenceFormat.PortableText)
        parts = canonical.split("+")
        if parts and parts[-1] == "Return":
            return "+".join([*parts[:-1], "Enter"])
        return canonical

    def _is_allowed_shortcut(self, canonical: str) -> bool:
        parts = canonical.split("+")
        if not parts:
            return True
        key = parts[-1]
        modifiers = set(parts[:-1])
        has_strong_modifier = bool(modifiers & {"Ctrl", "Alt", "Meta"})
        if has_strong_modifier:
            return True
        if modifiers:
            return False
        return key == "Esc" or self._is_function_key(key)

    def _is_function_key(self, key: str) -> bool:
        if not key.startswith("F"):
            return False
        try:
            number = int(key[1:])
        except ValueError:
            return False
        return 1 <= number <= 12
