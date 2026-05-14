#!/usr/bin/env python3
"""PySide6 application bootstrap for MindTask."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MindTask desktop UI")
    parser.add_argument("--config", help="Path to the MindTask config file")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_args)

    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print("PySide6 is not installed. Install it with: pip install -e .[ui]", file=sys.stderr)
            return 1
        raise

    from .main_window import MindTaskWindow
    from .style import THEME_SYSTEM, build_app_style

    app = QApplication([sys.argv[0]])
    app.setApplicationName("MindTask")
    app.setOrganizationName("MindTask")
    app.setStyle("Fusion")
    app.setProperty("mindtask_theme", THEME_SYSTEM)
    app.setStyleSheet(build_app_style(THEME_SYSTEM, app))

    window = MindTaskWindow(config_path=args.config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
