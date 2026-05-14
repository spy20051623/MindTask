"""CLI package exports for MindTask."""

from .cli import MindTaskCLI, main as cli_main
from .shell import MindTaskShell, main as shell_main

__all__ = ["MindTaskCLI", "MindTaskShell", "cli_main", "shell_main"]
