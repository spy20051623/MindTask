"""MCP package exports for MindTask."""

from typing import TYPE_CHECKING

from .tools import MindTaskMCPTools, get_mcp_tool_schemas

if TYPE_CHECKING:
    from .server import SimpleMindTaskMCPServer, main

__all__ = [
    "MindTaskMCPTools",
    "SimpleMindTaskMCPServer",
    "get_mcp_tool_schemas",
    "main",
]


def __getattr__(name):
    if name in {"SimpleMindTaskMCPServer", "main"}:
        from .server import SimpleMindTaskMCPServer, main

        values = {
            "SimpleMindTaskMCPServer": SimpleMindTaskMCPServer,
            "main": main,
        }
        return values[name]
    raise AttributeError(name)


def __dir__():
    return sorted(__all__)
