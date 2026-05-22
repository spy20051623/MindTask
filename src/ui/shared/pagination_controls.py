"""Reusable pagination controls for desktop list pages."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QIntValidator, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QStackedWidget, QWidget

from .pagination import PaginationState


PAGINATION_BUTTON_SIZE = 34
PAGINATION_PAGE_WIDTH = 58
PAGINATION_EDIT_WIDTH = 56
PAGINATION_EDIT_HEIGHT = 28
PAGINATION_HEIGHT = 34
PAGINATION_SPACING = 8
PAGINATION_WIDTH = PAGINATION_BUTTON_SIZE * 2 + PAGINATION_PAGE_WIDTH + PAGINATION_SPACING * 2


class PageJumpEdit(QLineEdit):
    """Line edit that lets Esc cancel page jump editing."""

    escapePressed = Signal()

    def event(self, event: object) -> bool:
        if (
            getattr(event, "type", lambda: None)() == QEvent.Type.ShortcutOverride
            and getattr(event, "key", lambda: None)() == Qt.Key.Key_Escape
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event: object) -> None:
        if getattr(event, "key", lambda: None)() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class PaginationControls(QWidget):
    """Compact previous/page/next control group."""

    previousRequested = Signal()
    nextRequested = Signal()
    pageRequested = Signal(int)

    def __init__(
        self,
        button_factory: Callable[[str, str, str, Callable[[], None]], QWidget],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("TransparentRow")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(PAGINATION_WIDTH, PAGINATION_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGINATION_SPACING)

        self.previous_button = button_factory("", "fa6s.chevron-left", "<", self.previousRequested.emit)
        self.next_button = button_factory("", "fa6s.chevron-right", ">", self.nextRequested.emit)
        self.previous_button.setFixedSize(PAGINATION_BUTTON_SIZE, PAGINATION_BUTTON_SIZE)
        self.next_button.setFixedSize(PAGINATION_BUTTON_SIZE, PAGINATION_BUTTON_SIZE)
        self.page_label = QLabel()
        self.page_label.setObjectName("MutedLabel")
        self.page_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.page_label.setFixedSize(PAGINATION_PAGE_WIDTH, 30)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setCursor(Qt.CursorShape.IBeamCursor)
        self.page_label.mousePressEvent = lambda _event: self.begin_page_edit()
        self.page_edit = PageJumpEdit()
        self.page_edit.setObjectName("PaginationPageEdit")
        self.page_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.page_edit.setFixedSize(PAGINATION_EDIT_WIDTH, PAGINATION_EDIT_HEIGHT)
        self.page_edit.setMinimumSize(PAGINATION_EDIT_WIDTH, PAGINATION_EDIT_HEIGHT)
        self.page_edit.setMaximumSize(PAGINATION_EDIT_WIDTH, PAGINATION_EDIT_HEIGHT)
        self.page_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_edit.returnPressed.connect(self.commit_page_edit)
        self.page_edit.editingFinished.connect(self.cancel_page_edit)
        self.page_edit.escapePressed.connect(self.cancel_page_edit)
        self.page_escape_shortcut = QShortcut(QKeySequence("Esc"), self.page_edit)
        self.page_escape_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.page_escape_shortcut.activated.connect(self.cancel_page_edit)
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("PaginationPageStack")
        self.page_stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.page_stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.page_stack.setFixedSize(PAGINATION_PAGE_WIDTH, 30)
        self.page_stack.setMinimumSize(PAGINATION_PAGE_WIDTH, 30)
        self.page_stack.setMaximumSize(PAGINATION_PAGE_WIDTH, 30)
        self.page_stack.addWidget(self.page_label)
        self.page_stack.addWidget(self.page_edit)

        layout.addWidget(self.previous_button)
        layout.addWidget(self.page_stack)
        layout.addWidget(self.next_button)
        self._total_pages = 1
        self._current_page = 1
        self._editing = False

    def set_tooltips(self, previous: str, next_text: str, page: str = "") -> None:
        self.previous_button.setToolTip(previous)
        self.previous_button.setAccessibleName(previous)
        self.next_button.setToolTip(next_text)
        self.next_button.setAccessibleName(next_text)
        self.page_label.setToolTip(page)
        self.page_label.setAccessibleName(page)
        self.page_edit.setToolTip(page)
        self.page_edit.setAccessibleName(page)

    def set_state(self, state: PaginationState, label: str) -> None:
        self._total_pages = state.total_pages
        self._current_page = state.current_page
        self.page_label.setText(label)
        if not self._editing:
            self.page_edit.setText(str(state.current_page))
            self.page_stack.setCurrentWidget(self.page_label)
        self.previous_button.setEnabled(state.can_previous)
        self.next_button.setEnabled(state.can_next)

    def begin_page_edit(self) -> None:
        self._editing = True
        self.page_edit.setText(str(self._current_page))
        self.page_edit.setValidator(QIntValidator(1, self._total_pages, self.page_edit))
        self.page_edit.selectAll()
        self.page_stack.setCurrentWidget(self.page_edit)
        self.page_edit.setFocus(Qt.FocusReason.MouseFocusReason)

    def cancel_page_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.page_edit.setText(str(self._current_page))
        self.page_stack.setCurrentWidget(self.page_label)

    def commit_page_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        text = self.page_edit.text().strip()
        self.page_stack.setCurrentWidget(self.page_label)
        if not text:
            return
        try:
            page = int(text)
        except ValueError:
            self.page_edit.setText(str(self._current_page))
            return
        page = max(1, min(page, self._total_pages))
        self.pageRequested.emit(page)
