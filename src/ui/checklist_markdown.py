"""Helpers for Markdown-backed task checklists."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional


CHECKLIST_ITEM_TEXT = "New item"
_CHECKLIST_RE = re.compile(r"^(\s*[-*]\s+\[)([ xX])(\]\s*)(.*)$")


@dataclass(frozen=True)
class ChecklistItem:
    line_index: int
    text: str
    completed: bool


def parse_checklist_items(markdown_text: str) -> List[ChecklistItem]:
    """Return checklist items found in simple Markdown task-list lines."""
    items: List[ChecklistItem] = []
    for line_index, line in enumerate((markdown_text or "").splitlines()):
        match = _CHECKLIST_RE.match(line)
        if not match:
            continue
        items.append(
            ChecklistItem(
                line_index=line_index,
                text=match.group(4).strip(),
                completed=match.group(2).lower() == "x",
            )
        )
    return items


def checklist_summary(markdown_text: str) -> tuple[int, int]:
    """Return completed and total checklist counts."""
    items = parse_checklist_items(markdown_text)
    return sum(1 for item in items if item.completed), len(items)


def toggle_checklist_item(markdown_text: str, item_index: int) -> str:
    """Flip a parsed checklist item's marker while preserving the line text."""
    items = parse_checklist_items(markdown_text)
    if item_index < 0 or item_index >= len(items):
        return markdown_text
    return toggle_checklist_item_line(markdown_text, items[item_index].line_index, items[item_index].text)


def toggle_checklist_item_line(markdown_text: str, line_index: int, expected_text: str) -> str:
    """Flip a checklist line only when its current text matches the UI text."""
    lines = (markdown_text or "").splitlines()
    if line_index < 0 or line_index >= len(lines):
        return markdown_text
    line = lines[line_index]
    match = _CHECKLIST_RE.match(line)
    if not match or match.group(4).strip() != expected_text:
        return markdown_text
    marker = " " if match.group(2).lower() == "x" else "x"
    lines[line_index] = f"{match.group(1)}{marker}{match.group(3)}{match.group(4)}"
    return "\n".join(lines)


def delete_checklist_item_line(markdown_text: str, line_index: int, expected_text: str) -> str:
    """Delete a checklist line only when its current text matches the UI text."""
    lines = (markdown_text or "").splitlines()
    if line_index < 0 or line_index >= len(lines):
        return markdown_text
    match = _CHECKLIST_RE.match(lines[line_index])
    if not match or match.group(4).strip() != expected_text:
        return markdown_text
    del lines[line_index]
    return "\n".join(lines)


def update_checklist_item_text_line(markdown_text: str, line_index: int, expected_text: str, new_text: str) -> str:
    """Rename a checklist line only when its current text matches the UI text."""
    lines = (markdown_text or "").splitlines()
    if line_index < 0 or line_index >= len(lines):
        return markdown_text
    match = _CHECKLIST_RE.match(lines[line_index])
    if not match or match.group(4).strip() != expected_text:
        return markdown_text
    text = new_text.strip()
    if not text:
        return markdown_text
    lines[line_index] = f"{match.group(1)}{match.group(2)}{match.group(3)}{text}"
    return "\n".join(lines)


def complete_all_checklist_items(markdown_text: str) -> str:
    """Mark every parsed checklist item as completed."""
    lines = (markdown_text or "").splitlines()
    changed = False
    for item in parse_checklist_items(markdown_text):
        if item.completed:
            continue
        line = lines[item.line_index]
        match = _CHECKLIST_RE.match(line)
        if match:
            lines[item.line_index] = f"{match.group(1)}x{match.group(3)}{match.group(4)}"
            changed = True
    return "\n".join(lines) if changed else markdown_text


def append_checklist_item(markdown_text: str, label: str = CHECKLIST_ITEM_TEXT) -> tuple[str, int]:
    """Append a new unchecked item and return the updated text plus line index."""
    text = markdown_text or ""
    lines = text.splitlines()
    new_line = f"- [ ] {label}"
    if lines and _CHECKLIST_RE.match(lines[-1]):
        lines.append(new_line)
    elif lines and lines[-1].strip():
        lines.extend(["", new_line])
    elif lines:
        lines.append(new_line)
    else:
        lines.append(new_line)
    return "\n".join(lines), len(lines) - 1


def checklist_item_text_span(markdown_text: str, line_index: int) -> Optional[tuple[int, int]]:
    """Return the character span for the editable text on a checklist line."""
    lines = (markdown_text or "").splitlines()
    if line_index < 0 or line_index >= len(lines):
        return None
    match = _CHECKLIST_RE.match(lines[line_index])
    if not match:
        return None
    offset = 0
    for index in range(line_index):
        offset += len(lines[index]) + 1
    start = offset + len(match.group(1)) + len(match.group(2)) + len(match.group(3))
    return start, start + len(match.group(4))


def render_checklist_markers(markdown_text: str) -> str:
    """Replace Markdown checklist markers with Qt-friendly checkbox glyph entities."""
    rendered_lines = []
    for line in (markdown_text or "").splitlines():
        match = _CHECKLIST_RE.match(line)
        if not match:
            rendered_lines.append(line)
            continue
        box = "&#9745;" if match.group(2).lower() == "x" else "&#9744;"
        rendered_lines.append(f"{match.group(1).replace('[', '')}{box} {match.group(4)}")
    return "\n".join(rendered_lines)
