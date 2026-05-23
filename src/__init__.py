"""MindTask package."""

from .core import MindTaskDB

__version__ = "1.2.11"
__author__ = "PY Shu"

__all__ = [
    "MindTaskDB",
    "MindTaskCLI",
]


def __getattr__(name):
    if name == "MindTaskCLI":
        from .cli import MindTaskCLI

        return MindTaskCLI

    raise AttributeError(name)
