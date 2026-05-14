# MCP Integration

MindTask exposes a line-delimited JSON-RPC server for MCP-style integrations.

## Run

```bash
python -m src.mcp.server
```

Use a custom config file:

```bash
python -m src.mcp.server --config path/to/mindtask.ini
```

Self-test:

```bash
python -m src.mcp.server --test
```

## Request Format

```json
{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}
```

Create task example:

```json
{"jsonrpc":"2.0","id":2,"method":"create_task","params":{"title":"Review notes","priority":2}}
```

Undo example:

```json
{"jsonrpc":"2.0","id":3,"method":"undo_last_operation","params":{}}
```

## Methods

- `list_projects`
- `list_tasks`
- `get_task`
- `create_task`
- `update_task`
- `complete_task`
- `delete_task`
- `get_stats`
- `search_tasks`
- `get_history`
- `undo_last_operation`
- `list_methods`
- `ping`
- `exit`
