"""Compact one-line alert message widget."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QSizePolicy, QWidget


ALERT_INFO = 0
ALERT_WARN = 1
ALERT_DANGER = 2
ALERT_SEVERITIES = {ALERT_INFO, ALERT_WARN, ALERT_DANGER}


class AlertMessage(QWidget):
    """Circle-exclamation icon plus a single line of alert text."""

    def __init__(self, text: str = "", severity: int = ALERT_INFO) -> None:
        super().__init__()
        self.setObjectName("AlertMessage")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.icon_label = QLabel("!")
        self.icon_label.setObjectName("AlertIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(18, 18)

        self.text_label = QLabel()
        self.text_label.setObjectName("AlertText")
        self.text_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.set_message(text, severity)

    def sizeHint(self) -> QSize:
        return self.layout().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.layout().minimumSize()

    def set_message(self, text: str, severity: int = ALERT_INFO) -> None:
        severity = severity if severity in ALERT_SEVERITIES else ALERT_INFO
        severity_text = str(severity)
        self.icon_label.setProperty("alertSeverity", severity_text)
        self.text_label.setProperty("alertSeverity", severity_text)
        self.text_label.setText(text)
        self.setVisible(bool(text))
        self._refresh_style(self.icon_label)
        self._refresh_style(self.text_label)

    def clear_message(self) -> None:
        self.set_message("")

    @staticmethod
    def _refresh_style(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
