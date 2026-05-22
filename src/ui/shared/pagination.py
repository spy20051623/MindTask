"""Shared pagination state for desktop lists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar


T = TypeVar("T")


@dataclass
class PaginationState:
    """Track page bounds and slice items without depending on Qt."""

    page_size: int
    page_index: int = 0
    total: int = 0

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def current_page(self) -> int:
        return self.page_index + 1

    @property
    def can_previous(self) -> bool:
        return self.total > self.page_size and self.page_index > 0

    @property
    def can_next(self) -> bool:
        return self.total > self.page_size and self.page_index < self.total_pages - 1

    @property
    def start(self) -> int:
        return self.page_index * self.page_size

    @property
    def end(self) -> int:
        return self.start + self.page_size

    def reset(self) -> None:
        self.page_index = 0

    def set_total(self, total: int) -> None:
        self.total = max(0, total)
        self.clamp()

    def clamp(self) -> None:
        self.page_index = max(0, min(self.page_index, self.total_pages - 1))

    def previous(self) -> None:
        self.page_index -= 1
        self.clamp()

    def next(self) -> None:
        self.page_index += 1
        self.clamp()

    def set_page_for_index(self, item_index: int) -> None:
        self.page_index = max(0, item_index) // self.page_size
        self.clamp()

    def set_current_page(self, page: int) -> None:
        self.page_index = max(1, page) - 1
        self.clamp()

    def items(self, items: Sequence[T]) -> Sequence[T]:
        self.set_total(len(items))
        return items[self.start : self.end]
