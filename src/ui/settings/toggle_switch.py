"""Small switch-style checkbox for settings."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QCheckBox, QStyleOptionButton

from ..shared.style import THEME_SYSTEM, colors_for_theme


class ToggleSwitch(QCheckBox):
    """A compact checkbox painted as an on/off switch."""

    def __init__(self, text: str = "", parent: object = None):
        super().__init__(text, parent)
        self._knob_position = 1.0 if self.isChecked() else 0.0
        self._animation = QPropertyAnimation(self, b"knobPosition", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate_to_state)

    def sizeHint(self) -> QSize:
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(54 + text_width, 22)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event: object) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)

        app = QApplication.instance()
        theme = THEME_SYSTEM
        if app is not None:
            theme = app.property("mindtask_theme") or THEME_SYSTEM
        colors = colors_for_theme(theme, app)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QRectF(0.5, 1.5, 38, 19)
        checked = self.isChecked()
        track_color = QColor("#16a34a" if checked else colors["disabled_bg"])
        border_color = QColor(colors["focus_border"] if self.hasFocus() else colors["border"])
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 9.5, 9.5)

        knob_x = 3.0 + (17.0 * self._knob_position)
        knob = QRectF(knob_x, 3.5, 15, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(knob)

        text_rect = QRectF(48, 0, max(0, self.width() - 48), self.height())
        painter.setPen(QColor(colors["text"] if self.isEnabled() else colors["disabled_text"]))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

    def _animate_to_state(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def _get_knob_position(self) -> float:
        return self._knob_position

    def _set_knob_position(self, value: float) -> None:
        self._knob_position = float(value)
        self.update()

    knobPosition = Property(float, _get_knob_position, _set_knob_position)
