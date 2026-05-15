"""MindTask package."""

from .core import MindTaskDB

__version__ = "1.1.4"
__author__ = "MindTask Team"

__all__ = [
    "MindTaskDB",
    "MindTaskCLI",
    "MindTaskMCPTools",
    "SimpleMindTaskMCPServer",
]


def __getattr__(name):
    if name == "MindTaskCLI":
        from .cli import MindTaskCLI

        return MindTaskCLI

    if name in {
        "MindTaskMCPTools",
        "SimpleMindTaskMCPServer",
    }:
        from .mcp import MindTaskMCPTools, SimpleMindTaskMCPServer

        values = {
            "MindTaskMCPTools": MindTaskMCPTools,
            "SimpleMindTaskMCPServer": SimpleMindTaskMCPServer,
        }
        return values[name]

    raise AttributeError(name)
