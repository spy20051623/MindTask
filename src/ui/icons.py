"""Icon helpers with text fallbacks for the desktop UI."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton

from .style import colors_for_theme

try:
    import qtawesome as qta
except ModuleNotFoundError:
    qta = None


def themed_icon(name: str, theme: str) -> QIcon:
    if qta is None:
        return QIcon()
    colors = colors_for_theme(theme, QApplication.instance())
    old_local_appdata = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = ""
    try:
        return qta.icon(name, color=colors["text"])
    except Exception:
        return QIcon()
    finally:
        if old_local_appdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local_appdata


def set_action_button_icon(button: QPushButton, icon_name: str, fallback_text: str, theme: str) -> None:
    icon = themed_icon(icon_name, theme)
    if icon.isNull():
        button.setIcon(QIcon())
        button.setText(fallback_text)
        return
    button.setText("")
    button.setIcon(icon)


def icon_button(tooltip: str, icon_name: str, fallback_text: str, theme: str, handler: Any) -> QPushButton:
    button = QPushButton()
    button.setObjectName("IconButton")
    button.setIconSize(QSize(18, 18))
    button.setFixedSize(34, 34)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    set_action_button_icon(button, icon_name, fallback_text, theme)
    button.clicked.connect(handler)
    return button
