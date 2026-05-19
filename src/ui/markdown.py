"""Markdown rendering helpers for the desktop UI."""

from __future__ import annotations

from markdown_it import MarkdownIt


_MARKDOWN = MarkdownIt("commonmark", {"html": False})


def render_markdown_html(markdown_text: str) -> str:
    """Render Markdown text to a small, Qt-friendly HTML document."""
    body = _MARKDOWN.render(markdown_text or "")
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    margin: 0;
    padding: 0;
}}
p {{
    margin: 0 0 8px 0;
}}
ul, ol {{
    margin: 0 0 8px 0;
    padding-left: 0;
}}
li {{
    margin: 0 0 4px 0;
}}
pre {{
    margin: 0 0 8px 0;
    padding: 6px;
}}
code {{
    font-family: Consolas, "Courier New", monospace;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""
