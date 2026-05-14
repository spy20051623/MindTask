#!/usr/bin/env python3
"""Initialize the MindTask database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core import MindTaskDB


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the MindTask SQLite database")
    parser.add_argument("--config", help="Path to the MindTask config file")
    args = parser.parse_args()

    db = MindTaskDB(config_path=args.config)
    db.initialize_database()
    print(f"Database initialized: {db.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
