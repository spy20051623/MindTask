#!/usr/bin/env python3
"""Simple JSON-RPC server for MindTask MCP-style integrations."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .tools import MindTaskMCPTools, get_mcp_tool_schemas


class SimpleMindTaskMCPServer:
    """Line-delimited JSON-RPC server."""

    def __init__(self, config_path: Optional[str] = None):
        self.tools = MindTaskMCPTools(config_path=config_path)
        self.running = True
        self.handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "list_projects": lambda **params: self.tools.list_projects(),
            "list_tasks": self.tools.list_tasks,
            "get_task": self.tools.get_task,
            "create_task": self.tools.create_task,
            "update_task": self._update_task,
            "complete_task": self.tools.complete_task,
            "delete_task": self.tools.delete_task,
            "get_stats": lambda **params: self.tools.get_stats(),
            "search_tasks": self.tools.search_tasks,
            "get_history": self.tools.get_history,
            "undo_last_operation": lambda **params: self.tools.undo_last_operation(),
            "list_methods": lambda **params: {
                "success": True,
                "data": {
                    "methods": sorted(self.handlers.keys()),
                    "schemas": get_mcp_tool_schemas(),
                },
            },
            "ping": lambda **params: {
                "success": True,
                "data": {
                    "message": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "server": "MindTask MCP Server",
                },
            },
            "exit": self._exit,
        }

    def _update_task(self, task_id: int, **params: Any) -> Dict[str, Any]:
        return self.tools.update_task(task_id, **params)

    def _exit(self, **params: Any) -> Dict[str, Any]:
        self.running = False
        return {"success": True, "data": {"message": "bye"}}

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        try:
            if not isinstance(params, dict):
                return self._json_error(request_id, -32602, "params must be an object")

            handler = self.handlers.get(method)
            if handler is None:
                return self._json_error(
                    request_id,
                    -32601,
                    f"Unknown method: {method}",
                    {"available_methods": sorted(self.handlers.keys())},
                )

            result = handler(**params)
            if result.get("success"):
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            return self._json_error(request_id, -32000, result.get("error", "Request failed"), result)

        except TypeError as exc:
            return self._json_error(request_id, -32602, str(exc))
        except Exception as exc:
            return self._json_error(
                request_id,
                -32603,
                str(exc),
                {"traceback": traceback.format_exc(), "timestamp": datetime.now().isoformat()},
            )

    def _json_error(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    def run_stdio(self) -> None:
        print("MindTask JSON-RPC server ready.", file=sys.stderr)
        for line in sys.stdin:
            if not self.running:
                break

            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                response = self._json_error(None, -32700, f"Invalid JSON: {exc}")
            else:
                response = self.handle_request(request)

            print(json.dumps(response, ensure_ascii=False))
            sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="MindTask JSON-RPC server")
    parser.add_argument("--config", help="Path to the MindTask config file")
    parser.add_argument("--test", action="store_true", help="Run a small self-test")
    args = parser.parse_args()

    server = SimpleMindTaskMCPServer(args.config)
    if args.test:
        for request in [
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "list_methods", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "get_stats", "params": {}},
        ]:
            print(json.dumps(server.handle_request(request), ensure_ascii=False, indent=2))
        return 0

    server.run_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
