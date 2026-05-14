"""MindTask package."""

from .core import MindTaskDB

__version__ = "1.0.0"
__author__ = "MindTask Team"

__all__ = [
    "MindTaskDB",
    "MindTaskCLI",
    "MindTaskShell",
    "MindTaskMCPTools",
    "SimpleMindTaskMCPServer",
]


def __getattr__(name):
    if name in {"MindTaskCLI", "MindTaskShell"}:
        from .cli import MindTaskCLI, MindTaskShell

        values = {
            "MindTaskCLI": MindTaskCLI,
            "MindTaskShell": MindTaskShell,
        }
        return values[name]

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
