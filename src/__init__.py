"""MindTask package."""

from .core import MindTaskDB
from .version import __author__, __version__

__all__ = [
    "MindTaskDB",
    "MindTaskCLI",
]


def __getattr__(name):
    if name == "MindTaskCLI":
        from .cli import MindTaskCLI

        return MindTaskCLI

    raise AttributeError(name)
