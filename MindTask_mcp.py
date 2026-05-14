#!/usr/bin/env python3
"""Compatibility entry point for the MindTask JSON-RPC server."""

from src.mcp.server import SimpleMindTaskMCPServer, main
from src.mcp.tools import MindTaskMCPTools, get_mcp_tool_schemas

__all__ = ["MindTaskMCPTools", "SimpleMindTaskMCPServer", "get_mcp_tool_schemas"]


if __name__ == "__main__":
    raise SystemExit(main())
