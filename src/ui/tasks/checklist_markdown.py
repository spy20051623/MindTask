"""Markdown-backed task checklist model."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


CHECKLIST_ITEM_TEXT = "New item"
_CHECKLIST_RE = re.compile(r"^(\s*[-*]\s+\[)([ xX])(\]\s*)(.*)$")


@dataclass(frozen=True)
class ChecklistItem:
    line_index: int
    text: str
    completed: bool


class ChecklistMarkdown:
    """Operations for checklist items embedded in Markdown text."""

    def __init__(self, text: str) -> None:
        self.text = text or ""

    def items(self) -> list[ChecklistItem]:
        items: list[ChecklistItem] = []
        for line_index, line in enumerate(self._lines()):
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

    def toggle_item(self, item_index: int) -> str:
        items = self.items()
        if item_index < 0 or item_index >= len(items):
            return self.text
        item = items[item_index]
        return self.toggle_line(item.line_index, item.text)

    def toggle_line(self, line_index: int, expected_text: str) -> str:
        lines = self._lines()
        match = self._matching_line(lines, line_index, expected_text)
        if not match:
            return self.text
        marker = " " if match.group(2).lower() == "x" else "x"
        lines[line_index] = f"{match.group(1)}{marker}{match.group(3)}{match.group(4)}"
        return "\n".join(lines)

    def delete_line(self, line_index: int, expected_text: str) -> str:
        lines = self._lines()
        match = self._matching_line(lines, line_index, expected_text)
        if not match:
            return self.text
        del lines[line_index]
        return "\n".join(lines)

    def update_text(self, line_index: int, expected_text: str, new_text: str) -> str:
        lines = self._lines()
        match = self._matching_line(lines, line_index, expected_text)
        if not match:
            return self.text
        text = new_text.strip()
        if not text:
            return self.text
        lines[line_index] = f"{match.group(1)}{match.group(2)}{match.group(3)}{text}"
        return "\n".join(lines)

    def complete_all(self) -> str:
        lines = self._lines()
        changed = False
        for item in self.items():
            if item.completed:
                continue
            match = _CHECKLIST_RE.match(lines[item.line_index])
            if match:
                lines[item.line_index] = f"{match.group(1)}x{match.group(3)}{match.group(4)}"
                changed = True
        return "\n".join(lines) if changed else self.text

    def append_item(self, label: str = CHECKLIST_ITEM_TEXT) -> tuple[str, int]:
        lines = self._lines()
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

    def item_text_span(self, line_index: int) -> Optional[tuple[int, int]]:
        lines = self._lines()
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

    def render_markers(self) -> str:
        rendered_lines = []
        for line in self._lines():
            match = _CHECKLIST_RE.match(line)
            if not match:
                rendered_lines.append(line)
                continue
            box = "&#9745;" if match.group(2).lower() == "x" else "&#9744;"
            rendered_lines.append(f"{match.group(1).replace('[', '')}{box} {match.group(4)}")
        return "\n".join(rendered_lines)

    def _lines(self) -> list[str]:
        return self.text.splitlines()

    def _matching_line(self, lines: list[str], line_index: int, expected_text: str) -> Optional[re.Match[str]]:
        if line_index < 0 or line_index >= len(lines):
            return None
        match = _CHECKLIST_RE.match(lines[line_index])
        if not match or match.group(4).strip() != expected_text:
            return None
        return match
