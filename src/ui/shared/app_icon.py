"""Application icon helpers."""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path


def app_icon_path(filename: str = "mindtask-icon.png") -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets" / "icons" / filename
    return Path(resources.files("src.ui") / "assets" / "icons" / filename)
