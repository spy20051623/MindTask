#!/usr/bin/env python3
"""PySide6 application bootstrap for MindTask."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MindTask desktop UI")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_args)

    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication, QDialog
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print("PySide6 is not installed. Install it with: pip install -e .[ui]", file=sys.stderr)
            return 1
        raise

    try:
        from ..core import DatabaseInvalidError, DatabaseMissingError, find_config_path, load_config

        config_path = find_config_path()
        first_run = config_path is None
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    from .database_unavailable import DatabaseUnavailableDialog
    from .main_window import MindTaskWindow
    from .shared.app_icon import app_icon_path
    from .shared.style import THEME_SYSTEM, build_app_style
    from .welcome import WelcomeDialog

    app = QApplication([sys.argv[0]])
    app.setApplicationName("MindTask")
    app.setOrganizationName("MindTask")
    app.setWindowIcon(QIcon(str(app_icon_path())))
    app.setStyle("Fusion")
    app.setProperty("mindtask_theme", THEME_SYSTEM)
    app.setStyleSheet(build_app_style(THEME_SYSTEM, app))

    if first_run:
        welcome = WelcomeDialog()
        if welcome.exec() != QDialog.DialogCode.Accepted:
            return 0
        config_path = welcome.config_path

    while True:
        try:
            window = MindTaskWindow(config_path=str(config_path))
            break
        except (DatabaseMissingError, DatabaseInvalidError) as exc:
            language = load_config(str(config_path)).ui_language
            reason = "missing" if isinstance(exc, DatabaseMissingError) else "invalid"
            dialog = DatabaseUnavailableDialog(
                config_path=str(config_path),
                database_path=str(exc),
                language=language,
                reason=reason,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
