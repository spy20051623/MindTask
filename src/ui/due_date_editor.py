"""Reusable due-date editor for desktop task forms."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from PySide6.QtCore import QDate, QEvent
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QWidget

from .i18n import Translator


DUE_DAY_END_SAME_DAY = "same_day"
DUE_DAY_END_NEXT_DAY_EARLY_MORNING = "next_day_early_morning"
DUE_DAY_END_OPTIONS = (DUE_DAY_END_SAME_DAY, DUE_DAY_END_NEXT_DAY_EARLY_MORNING)
TIME_SLOT_MINUTES = 30


class DueDateEditor(QWidget):
    """A date picker with optional exact time for task due dates."""

    def __init__(self, due_day_end: str = DUE_DAY_END_SAME_DAY, language: str = "en", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.due_day_end = due_day_end if due_day_end in DUE_DAY_END_OPTIONS else DUE_DAY_END_SAME_DAY
        self.translator = Translator(language)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.time_mode_combo = QComboBox()
        self.time_mode_combo.currentIndexChanged.connect(self._update_enabled_state)
        layout.addWidget(self.time_mode_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._enable_due_date)
        self.date_edit.installEventFilter(self)
        layout.addWidget(self.date_edit)

        self.time_combo = QComboBox()
        self.time_combo.setEditable(True)
        self.time_combo.setMinimumWidth(110)
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

    def set_due_day_end(self, due_day_end: str) -> None:
        if due_day_end in DUE_DAY_END_OPTIONS:
            self.due_day_end = due_day_end

    def set_due_value(self, value: Optional[str]) -> None:
        if not value:
            self._set_time_mode("none")
            self._update_enabled_state()
            return

        due = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        display_date = due.date()
        exact_time = True
        due_time = due.time().strftime("%H:%M:%S")
        if self.due_day_end == DUE_DAY_END_SAME_DAY and due_time == "23:59:59":
            exact_time = False
        elif self.due_day_end == DUE_DAY_END_NEXT_DAY_EARLY_MORNING and due_time == "04:59:59":
            display_date = (due - timedelta(days=1)).date()
            exact_time = False

        self.date_edit.setDate(QDate(display_date.year, display_date.month, display_date.day))
        self._set_time_mode("exact_time" if exact_time else "all_day")
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

        if self.due_day_end == DUE_DAY_END_NEXT_DAY_EARLY_MORNING:
            due = datetime.combine(selected_date + timedelta(days=1), datetime.min.time()).replace(
                hour=4,
                minute=59,
                second=59,
            )
            return due.strftime("%Y-%m-%d %H:%M:%S")

        due = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59, second=59)
        return due.strftime("%Y-%m-%d %H:%M:%S")

    def clear(self) -> None:
        self.set_due_value(None)

    def _update_enabled_state(self) -> None:
        self.time_combo.setEnabled(True)

    def _enable_due_date(self) -> None:
        if self.time_mode_combo.currentData() == "none":
            self._set_time_mode("all_day")

    def _enable_exact_time(self) -> None:
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
        text = value.strftime("%H:%M:%S") if value.second else value.strftime("%H:%M")
        self.time_combo.blockSignals(True)
        self.time_combo.setCurrentText(text)
        self.time_combo.blockSignals(False)

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
        interactive_events = {
            QEvent.Type.FocusIn,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
        }
        if event.type() in interactive_events:
            if watched == self.date_edit:
                self._enable_due_date()
            elif watched == self.time_combo:
                self._enable_exact_time()
        return super().eventFilter(watched, event)
