# Iteration Log

This file is maintained by version.

Update it immediately before creating a release commit, not after every local change. Each entry should describe the user-visible or project-level outcome of that version.

## Format

```text
## <version> - <YYYY-MM-DD>

- Summary: <one sentence>
- Changed: <notable implementation or documentation changes>
- Verified: <checks run before release commit>
```

## Entries

## 1.0.0 - 2026-05-14

- Summary: Prepare MindTask 1.0.0 with cleaned project structure, configuration-driven database access, operation history, undo support, and documented CLI/MCP workflows.
- Changed: Rebuilt the core SQLite layer, CLI, shell, MCP JSON-RPC server, schema, docs, tests, configuration, history tracking, and version command.
- Verified: Ran Python compile checks, CLI smoke checks, MCP self-test, and manual history/undo validation with Python 3.10.11.
