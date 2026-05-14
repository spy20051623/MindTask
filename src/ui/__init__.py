"""Desktop UI package for MindTask."""

__all__ = ["main"]


def main() -> int:
    from .app import main as run

    return run()
