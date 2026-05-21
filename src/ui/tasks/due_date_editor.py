"""Reusable due-date editor for desktop task forms."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QDateEdit, QHBoxLayout, QWidget

from ..shared.i18n import Translator


NO_DUE_DATE = QDate(1900, 1, 1)
NO_DUE_DATE_TEXT = "YYYY-MM-DD"
NO_DUE_TIME_TEXT = "HH:MM"
TIME_SLOT_MINUTES = 30
TIME_MODE_WIDTH = 116
DATE_WIDTH = 128
TIME_WIDTH = 100


class NoWheelComboBox(QComboBox):
    """Combo box that ignores accidental wheel changes."""

    def wheelEvent(self, event: QEvent) -> None:
        event.ignore()


class NoWheelDateEdit(QDateEdit):
    """Date edit without wheel or click-stepper value changes."""

    def wheelEvent(self, event: QEvent) -> None:
        event.ignore()


class DueDateEditor(QWidget):
    """A date picker with optional exact time for task due dates."""

    def __init__(self, language: str = "en", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.translator = Translator(language)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.time_mode_combo = NoWheelComboBox()
        self.time_mode_combo.setFixedWidth(TIME_MODE_WIDTH)
        self.time_mode_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.time_mode_combo.installEventFilter(self)
        self.time_mode_combo.currentIndexChanged.connect(self._handle_time_mode_changed)
        layout.addWidget(self.time_mode_combo)

        self.date_edit = NoWheelDateEdit()
        self.date_edit.setFixedWidth(DATE_WIDTH)
        self.date_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.date_edit.setMinimumDate(NO_DUE_DATE)
        self.date_edit.setSpecialValueText(NO_DUE_DATE_TEXT)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._enable_due_date)
        self.date_edit.installEventFilter(self)
        layout.addWidget(self.date_edit)

        self.time_combo = NoWheelComboBox()
        self.time_combo.setEditable(True)
        self.time_combo.setFixedWidth(TIME_WIDTH)
        self.time_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if self.time_combo.lineEdit() is not None:
            self.time_combo.lineEdit().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.time_combo.lineEdit().installEventFilter(self)
        for hour in range(24):
            for minute in range(0, 60, TIME_SLOT_MINUTES):
                self.time_combo.addItem(f"{hour:02d}:{minute:02d}")
        self._set_time_value(self._next_half_hour())
        self.time_combo.currentTextChanged.connect(self._enable_exact_time)
        self.time_combo.installEventFilter(self)
        layout.addWidget(self.time_combo)
        layout.addStretch()

        self.retranslate(language)
        self.set_due_value(None)

    def retranslate(self, language: str) -> None:
        self.translator.set_language(language)
        current_mode = self.time_mode_combo.currentData()
        self.time_mode_combo.blockSignals(True)
        self.time_mode_combo.clear()
        self.time_mode_combo.addItem(self.translator.text("no_due_date"), "none")
        self.time_mode_combo.addItem(self.translator.text("all_day"), "all_day")
        self.time_mode_combo.addItem(self.translator.text("exact_time"), "exact_time")
        self.time_mode_combo.blockSignals(False)
        self._set_time_mode(str(current_mode or "none"))
        self.date_edit.setToolTip(self.translator.text("due_date_picker"))
        self.time_combo.setToolTip(self.translator.text("due_time_picker"))

    def set_due_value(self, value: Optional[str], due_mode: Optional[str] = None) -> None:
        if not value:
            self._show_no_due_placeholders()
            self._set_time_mode("none")
            self._update_enabled_state()
            return

        due = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        if due_mode == "all_day":
            self.date_edit.setDate(QDate(due.year, due.month, due.day))
            self._set_time_mode("all_day")
            self._show_time_placeholder()
            self._update_enabled_state()
            return
        if due_mode == "exact_time":
            self.date_edit.setDate(QDate(due.year, due.month, due.day))
            self._set_time_mode("exact_time")
            self._set_time_value(due.time())
            self._update_enabled_state()
            return

        self.date_edit.setDate(QDate(due.year, due.month, due.day))
        self._set_time_mode("exact_time")
        self._set_time_value(due.time())
        self._update_enabled_state()

    def due_value(self) -> Optional[str]:
        if self.time_mode_combo.currentData() == "none":
            return None

        selected_date = self.date_edit.date().toPython()
        if self.time_mode_combo.currentData() == "exact_time":
            selected_time = self._selected_time()
            due = datetime.combine(selected_date, selected_time)
            return due.strftime("%Y-%m-%d %H:%M:%S")

        due = datetime.combine(selected_date, datetime.min.time())
        return due.strftime("%Y-%m-%d %H:%M:%S")

    def due_mode(self) -> str:
        mode = self.time_mode_combo.currentData()
        return str(mode or "none")

    def due_parts(self) -> tuple[str, Optional[str], Optional[str]]:
        mode = self.due_mode()
        if mode == "none":
            return mode, None, None
        date_text = self.date_edit.date().toString("yyyy-MM-dd")
        if mode == "all_day":
            return mode, date_text, None
        try:
            selected_time = self._selected_time()
        except ValueError:
            return mode, date_text, self.time_combo.currentText().strip()
        return mode, date_text, self._format_time_part(selected_time)

    def invalid_parts(self) -> tuple[bool, bool]:
        mode = self.due_mode()
        if mode == "none":
            return False, False
        date_invalid = self.date_edit.date() == NO_DUE_DATE or not self.date_edit.hasAcceptableInput()
        time_invalid = False
        if mode == "exact_time":
            try:
                self._selected_time()
            except ValueError:
                time_invalid = True
        return date_invalid, time_invalid

    def clear(self) -> None:
        self.set_due_value(None)

    def _update_enabled_state(self) -> None:
        self.time_combo.setEnabled(True)

    def _handle_time_mode_changed(self) -> None:
        mode = self.time_mode_combo.currentData()
        if mode == "none":
            self._show_no_due_placeholders()
        elif mode == "all_day":
            self._fill_default_date()
            self._show_time_placeholder()
        elif mode == "exact_time":
            self._fill_default_date()
            if self.time_combo.currentText().strip() == NO_DUE_TIME_TEXT:
                self._set_time_value(self._next_half_hour())
        self._update_enabled_state()

    def _enable_due_date(self) -> None:
        self._fill_default_date()
        if self.time_mode_combo.currentData() == "none":
            self._set_time_mode("all_day")

    def _enable_exact_time(self) -> None:
        self._fill_default_date()
        if self.time_combo.currentText().strip() == NO_DUE_TIME_TEXT:
            self._set_time_value(self._next_half_hour())
        if self.time_mode_combo.currentData() != "exact_time":
            self._set_time_mode("exact_time")

    def _set_time_mode(self, mode: str) -> None:
        for index in range(self.time_mode_combo.count()):
            if self.time_mode_combo.itemData(index) == mode:
                self.time_mode_combo.setCurrentIndex(index)
                return
        if self.time_mode_combo.count():
            self.time_mode_combo.setCurrentIndex(0)

    def _set_time_value(self, value: time) -> None:
        text = self._format_time_part(value)
        self.time_combo.blockSignals(True)
        self.time_combo.setCurrentText(text)
        self.time_combo.blockSignals(False)

    def _format_time_part(self, value: time) -> str:
        return value.strftime("%H:%M:%S") if value.second else value.strftime("%H:%M")

    def _show_no_due_placeholders(self) -> None:
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(NO_DUE_DATE)
        self.date_edit.blockSignals(False)
        self.time_combo.blockSignals(True)
        self.time_combo.setCurrentText(NO_DUE_TIME_TEXT)
        self.time_combo.blockSignals(False)

    def _show_time_placeholder(self) -> None:
        self.time_combo.blockSignals(True)
        self.time_combo.setCurrentText(NO_DUE_TIME_TEXT)
        self.time_combo.blockSignals(False)

    def _fill_default_date(self) -> None:
        if self.date_edit.date() != NO_DUE_DATE:
            return
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.blockSignals(False)

    def _selected_time(self) -> time:
        value = self.time_combo.currentText().strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                pass
        raise ValueError(self.translator.text("invalid_time"))

    def _next_half_hour(self) -> time:
        now = datetime.now()
        base = now.replace(second=0, microsecond=0)
        minutes_to_add = TIME_SLOT_MINUTES - (base.minute % TIME_SLOT_MINUTES)
        if minutes_to_add == 0:
            minutes_to_add = TIME_SLOT_MINUTES
        return (base + timedelta(minutes=minutes_to_add)).time().replace(second=0, microsecond=0)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel and watched in (
            self.time_mode_combo,
            self.date_edit,
            self.time_combo,
            self.time_combo.lineEdit(),
        ):
            event.ignore()
            return True
        interactive_events = {
            QEvent.Type.FocusIn,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
        }
        if event.type() in interactive_events:
            if watched == self.date_edit:
                self._enable_due_date()
            elif watched in (self.time_combo, self.time_combo.lineEdit()):
                self._enable_exact_time()
        return super().eventFilter(watched, event)
