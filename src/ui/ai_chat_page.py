"""AI chat page for the desktop window."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QEvent, QThread, Signal, Qt
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import AIChatService, AIChatTurnResult, MindTaskDB
from .shared.alert_message import ALERT_WARN, AlertMessage
from .shared.icons import colored_icon, set_danger_button_icon
from .tasks.markdown import render_markdown_html


AI_ACTION_STATUS_META = {
    "pending": ("ai_action_status_pending", "fa6s.clock", None),
    "running": ("ai_action_status_running", "fa6s.spinner", "#f59e0b"),
    "ok": ("ai_action_status_ok", "fa6s.circle-check", "#16a34a"),
    "error": ("ai_action_status_error", "fa6s.circle-xmark", "#dc2626"),
    "rejected": ("ai_action_status_rejected", "fa6s.ban", "#dc2626"),
    "skipped": ("ai_action_status_skipped", "fa6s.forward-step", "#9ca3af"),
}
AI_TOOL_LABEL_KEYS = {
    "get_task": "ai_tool_get_task",
    "get_tasks": "ai_tool_get_tasks",
    "search_tasks": "ai_tool_search_tasks",
    "get_projects": "ai_tool_get_projects",
    "get_project": "ai_tool_get_project",
    "get_project_summaries": "ai_tool_get_project_summaries",
    "get_stats": "ai_tool_get_stats",
    "get_history": "ai_tool_get_history",
    "get_task_history": "ai_tool_get_task_history",
    "create_task": "ai_tool_create_task",
    "update_task": "ai_tool_update_task",
    "delete_task": "ai_tool_delete_task",
    "complete_task": "ai_tool_complete_task",
    "create_project": "ai_tool_create_project",
    "update_project": "ai_tool_update_project",
    "delete_empty_project": "ai_tool_delete_empty_project",
}


class AIMarkdownBody(QTextBrowser):
    """Markdown message body that grows with content instead of scrolling inside."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class AIMessageCard(QFrame):
    """One chat message rendered as a compact card."""

    def __init__(
        self,
        role: str,
        role_label: str,
        content: str,
        meta: str = "",
        *,
        metadata: Optional[Dict[str, Any]] = None,
        header_status: str = "",
        approval_handlers: Optional[Dict[str, Any]] = None,
        batch_undo_handler: Optional[Any] = None,
        batch_undone: bool = False,
        tool_labels: Optional[Dict[str, str]] = None,
        detail_labels: Optional[Dict[str, str]] = None,
        status_labels: Optional[Dict[str, str]] = None,
        size_changed: Optional[Any] = None,
        theme: str = "dark",
    ) -> None:
        super().__init__()
        self.action_detail_labels: List[QLabel] = []
        self.size_changed = size_changed
        self.theme = theme
        self.tool_labels = tool_labels or {}
        self.detail_labels = detail_labels or {}
        self.status_labels = status_labels or {}
        self.batch_undo_handler = batch_undo_handler
        self.batch_undone = batch_undone
        self.setObjectName("AIUserMessage" if role == "user" else "AIAssistantMessage")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 11)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        role_text = QLabel(role_label)
        role_text.setObjectName("AIMessageRole")
        header.addWidget(role_text)
        self.header_status_label = QLabel(header_status)
        self.header_status_label.setObjectName("AIMessageHeaderStatus")
        header.addWidget(self.header_status_label)
        self.header_status_label.setVisible(bool(header_status))
        header.addStretch()
        if meta:
            meta_text = QLabel(meta)
            meta_text.setObjectName("AIMessageMeta")
            header.addWidget(meta_text)
        layout.addLayout(header)

        body = AIMarkdownBody()
        body.setObjectName("AIMessageBody")
        body.setFrameShape(QFrame.Shape.NoFrame)
        body.setOpenExternalLinks(True)
        body.setReadOnly(True)
        body.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.document().setDocumentMargin(0)
        body.document().setIndentWidth(16)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body_label = body
        layout.addWidget(body)
        self.set_body_content(content)

        if role == "assistant" and metadata:
            self.add_actions_section(layout, metadata, approval_handlers or {})

    def add_actions_section(
        self,
        layout: QVBoxLayout,
        metadata: Dict[str, Any],
        approval_handlers: Dict[str, Any],
    ) -> None:
        actions = [action for action in metadata.get("actions", []) if isinstance(action, dict)]
        if not actions:
            return
        results = [result for result in metadata.get("action_results", []) if isinstance(result, dict)]
        status = str(metadata.get("approval_status") or "pending")
        layout.addSpacing(6)
        separator = QFrame()
        separator.setObjectName("AIActionSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)
        layout.addSpacing(6)
        for index, action in enumerate(actions):
            self.add_action_row(layout, index, action, results[index] if index < len(results) else None)
        if status == "pending" and approval_handlers:
            buttons = QHBoxLayout()
            buttons.setContentsMargins(0, 2, 0, 0)
            buttons.setSpacing(8)
            allow_all = QPushButton(self.action_detail_label("allow_all", "Allow all"))
            allow_once = QPushButton(self.action_detail_label("allow_once", "Allow once"))
            allow_once.setObjectName("SecondaryButton")
            reject = QPushButton(self.action_detail_label("reject_remaining", "Reject remaining"))
            reject.setObjectName("DangerButton")
            allow_all.clicked.connect(approval_handlers.get("allow_all"))
            allow_once.clicked.connect(approval_handlers.get("allow_once"))
            reject.clicked.connect(approval_handlers.get("reject"))
            buttons.addWidget(allow_all)
            buttons.addWidget(allow_once)
            buttons.addWidget(reject)
            buttons.addStretch()
            layout.addLayout(buttons)
        elif self.batch_undone or self.batch_undo_handler is not None:
            buttons = QHBoxLayout()
            buttons.setContentsMargins(0, 4, 0, 0)
            buttons.setSpacing(8)
            if self.batch_undone:
                undone_label = QLabel(self.action_detail_label("batch_undone", "Rolled back"))
                undone_label.setObjectName("AIActionTitle")
                buttons.addWidget(undone_label)
            else:
                undo_button = QPushButton(self.action_detail_label("undo_batch", "Roll back"))
                undo_button.setObjectName("DangerButton")
                undo_button.clicked.connect(self.batch_undo_handler)
                buttons.addWidget(undo_button)
            buttons.addStretch()
            layout.addLayout(buttons)

    def add_action_row(
        self,
        layout: QVBoxLayout,
        index: int,
        action: Dict[str, Any],
        result: Optional[Dict[str, Any]],
    ) -> None:
        tool = str(action.get("tool") or action.get("name") or action.get("type") or "")
        arguments = action.get("arguments") or action.get("args") or {}
        status = self.action_result_status(result)
        status_key, icon_name, color = self.action_status_meta(status)
        status_label = self.action_status_text(status_key)
        display_name = self.action_tool_display_name(tool)
        button = QToolButton()
        button.setObjectName("AIActionToggle")
        button.setCheckable(True)
        button.setChecked(False)
        button.setText(f"{index + 1}. {display_name} · {status_label}")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(14, 14))
        icon_color = color or ("#e7e7e7" if self.theme == "dark" else "#1f2937")
        icon = colored_icon(icon_name, icon_color)
        if not icon.isNull():
            button.setIcon(icon)
        if color:
            button.setStyleSheet(f"QToolButton#AIActionToggle {{ color: {color}; border-color: {color}; }}")
        detail = QLabel(self.action_detail_text(tool, arguments, result))
        detail.setObjectName("AIActionDetail")
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail.hide()
        button.toggled.connect(detail.setVisible)
        button.toggled.connect(lambda _checked=False: self.notify_size_changed())
        layout.addWidget(button)
        layout.addWidget(detail)
        self.action_detail_labels.append(detail)

    def notify_size_changed(self) -> None:
        if self.size_changed:
            self.size_changed(self)

    def set_content(self, content: str) -> None:
        self.set_body_content(content)
        self.fit_to_width(self.width())
        self.notify_size_changed()

    def set_body_content(self, content: str) -> None:
        self.body_label.setVisible(bool(content.strip()))
        self.body_label.setHtml(render_markdown_html(content))
        self.update_body_height(max(120, self.width() - 28))

    def set_header_status(self, status: str) -> None:
        self.header_status_label.setText(status)
        self.header_status_label.setVisible(bool(status))
        self.notify_size_changed()

    def action_tool_display_name(self, tool: str) -> str:
        return self.tool_labels.get(tool) or tool

    def action_detail_label(self, key: str, fallback: str) -> str:
        return self.detail_labels.get(key) or fallback

    def action_detail_text(self, tool: str, arguments: Any, result: Optional[Dict[str, Any]]) -> str:
        lines = [
            f"{self.action_detail_label('tool', 'Tool')}: {tool}",
            "",
            f"{self.action_detail_label('arguments', 'Arguments')}:",
            json.dumps(arguments, ensure_ascii=False, sort_keys=True, indent=2),
        ]
        if result:
            if result.get("status"):
                lines.extend(["", f"{self.action_detail_label('status', 'Status')}:", str(result["status"])])
            if result.get("error"):
                lines.extend(["", f"{self.action_detail_label('error', 'Error')}:", str(result["error"])])
            value = result.get("result")
            if result.get("result_type") == "json":
                value_text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            else:
                value_text = str(value)
            lines.extend(["", f"{self.action_detail_label('result', 'Result')}:", value_text])
        else:
            lines.extend(["", f"{self.action_detail_label('result', 'Result')}: {self.action_detail_label('waiting', 'waiting for execution')}"])
        return "\n".join(lines)

    def action_status_text(self, status: str) -> str:
        return {
            "pending": self.status_labels.get("approval_pending", "Pending"),
            "approved": self.status_labels.get("approval_approved", "Approved"),
            "rejected": self.status_labels.get("approval_rejected", "Rejected"),
            "executed": self.status_labels.get("approval_executed", "Executed"),
            "failed": self.status_labels.get("approval_failed", "Failed"),
            "running": self.status_labels.get("approval_running", "Running"),
            "ai_action_status_pending": self.status_labels.get("pending", "Pending"),
            "ai_action_status_running": self.status_labels.get("running", "Running"),
            "ai_action_status_ok": self.status_labels.get("ok", "Succeeded"),
            "ai_action_status_error": self.status_labels.get("error", "Failed"),
            "ai_action_status_rejected": self.status_labels.get("rejected", "Rejected"),
            "ai_action_status_skipped": self.status_labels.get("skipped", "Skipped"),
        }.get(status, status)

    def action_result_status(self, result: Optional[Dict[str, Any]]) -> str:
        if not result:
            return "pending"
        status = str(result.get("status") or "").strip()
        return status or "pending"

    def action_status_meta(self, status: str) -> tuple[str, str, Optional[str]]:
        return AI_ACTION_STATUS_META.get(status, (status or "ai_action_status_pending", "fa6s.clock", None))

    def fit_to_width(self, width: int) -> None:
        width = max(260, int(width))
        self.setFixedWidth(width)
        body_width = max(120, width - 28)
        self.body_label.setFixedWidth(body_width)
        self.update_body_height(body_width)
        for label in self.action_detail_labels:
            label.setFixedWidth(max(120, width - 28))
        self.adjustSize()
        self.setMinimumHeight(self.sizeHint().height())

    def update_body_height(self, width: int) -> None:
        body_width = max(120, width)
        self.body_label.document().setTextWidth(body_width)
        body_height = math.ceil(self.body_label.document().size().height()) + 8
        self.body_label.setFixedHeight(max(24, body_height))


class AIChatWorker(QThread):
    """Run slow AI requests away from the UI thread."""

    result_ready = Signal(object)
    progress_ready = Signal()
    chunk_ready = Signal(str)
    stream_reset_ready = Signal()
    error_ready = Signal(str)

    def __init__(
        self,
        db: MindTaskDB,
        mode: str,
        *,
        content: str = "",
        session_id: Optional[int] = None,
        user_message_id: Optional[int] = None,
        assistant_message_id: Optional[int] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        allow_follow_up_actions: bool = False,
    ) -> None:
        super().__init__()
        self.db = db
        self.mode = mode
        self.content = content
        self.session_id = session_id
        self.user_message_id = user_message_id
        self.assistant_message_id = assistant_message_id
        self.actions = actions or []
        self.allow_follow_up_actions = allow_follow_up_actions

    def run(self) -> None:
        try:
            service = AIChatService(self.db)
            if self.mode == "send":
                result = service.send_user_message(
                    self.content,
                    session_id=self.session_id,
                    on_chunk=self.chunk_ready.emit,
                    on_stream_reset=self.stream_reset_ready.emit,
                    should_cancel=self.isInterruptionRequested,
                )
            elif self.mode == "approve":
                if self.session_id is None or self.user_message_id is None:
                    raise ValueError("Approval is missing the original AI chat message.")
                result = service.continue_after_approval(
                    session_id=self.session_id,
                    user_message_id=self.user_message_id,
                    assistant_message_id=self.assistant_message_id,
                    actions=self.actions,
                    allow_follow_up_actions=self.allow_follow_up_actions,
                    after_execution=self.progress_ready.emit,
                    on_chunk=self.chunk_ready.emit,
                    on_stream_reset=self.stream_reset_ready.emit,
                    should_cancel=self.isInterruptionRequested,
                )
            elif self.mode == "reject":
                if self.session_id is None or self.user_message_id is None:
                    raise ValueError("Rejection is missing the original AI chat message.")
                result = service.reject_pending_actions(
                    session_id=self.session_id,
                    user_message_id=self.user_message_id,
                    assistant_message_id=self.assistant_message_id,
                    after_execution=self.progress_ready.emit,
                    on_chunk=self.chunk_ready.emit,
                    on_stream_reset=self.stream_reset_ready.emit,
                    should_cancel=self.isInterruptionRequested,
                )
            else:
                raise ValueError("Unsupported AI chat worker mode.")
        except Exception as exc:
            self.error_ready.emit(str(exc))
            return
        self.result_ready.emit(result)


class AIChatPageMixin:
    """Mixin for the AI chat page."""

    def _build_ai_chat_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        self.ai_chat_sessions_label = self._section_label("")
        sidebar_layout.addWidget(self.ai_chat_sessions_label)
        session_actions = QHBoxLayout()
        session_actions.setContentsMargins(0, 0, 0, 0)
        session_actions.setSpacing(8)
        self.ai_new_chat_button = QPushButton()
        self.ai_new_chat_button.setObjectName("SecondaryButton")
        self.ai_new_chat_button.clicked.connect(self.create_ai_chat_session_from_ui)
        self.ai_delete_chat_button = self._icon_button("", "fa6s.trash", "Del", self.delete_selected_ai_chat_session)
        self.ai_delete_chat_button.setObjectName("DangerIconButton")
        self.ai_delete_chat_button.setFixedSize(28, 28)
        self.ai_delete_chat_button.setIconSize(QSize(15, 15))
        session_actions.addWidget(self.ai_new_chat_button, 1)
        session_actions.addWidget(self.ai_delete_chat_button)
        sidebar_layout.addLayout(session_actions)

        self.ai_chat_session_list = QListWidget()
        self.ai_chat_session_list.setObjectName("AIChatSessionList")
        self.ai_chat_session_list.currentItemChanged.connect(self.handle_ai_chat_session_changed)
        sidebar_layout.addWidget(self.ai_chat_session_list, 1)
        self.ai_delete_all_chats_button = QPushButton()
        self.ai_delete_all_chats_button.setObjectName("DangerButton")
        self.ai_delete_all_chats_button.clicked.connect(self.delete_all_ai_chat_sessions_from_ui)
        sidebar_layout.addWidget(self.ai_delete_all_chats_button)

        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(10)

        header = QHBoxLayout()
        self.ai_chat_title_label = self._section_label("")
        self.ai_chat_status_label = AlertMessage()
        self.ai_chat_status_label.hide()
        header.addWidget(self.ai_chat_title_label)
        header.addWidget(self.ai_chat_status_label)
        header.addStretch()
        panel_layout.addLayout(header)

        self.ai_chat_messages_scroll = QScrollArea()
        self.ai_chat_messages_scroll.setObjectName("AIChatMessagesScroll")
        self.ai_chat_messages_scroll.setWidgetResizable(True)
        self.ai_chat_messages_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ai_chat_messages_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ai_chat_messages_scroll.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.ai_chat_messages_scroll.verticalScrollBar().setSingleStep(24)
        self.ai_chat_messages_scroll.viewport().installEventFilter(self)
        self.ai_chat_messages_container = QWidget()
        self.ai_chat_messages_container.setObjectName("AIMessageContainer")
        self.ai_chat_messages_layout = QVBoxLayout(self.ai_chat_messages_container)
        self.ai_chat_messages_layout.setContentsMargins(0, 0, 8, 0)
        self.ai_chat_messages_layout.setSpacing(10)
        self.ai_chat_messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.ai_chat_messages_scroll.setWidget(self.ai_chat_messages_container)
        panel_layout.addWidget(self.ai_chat_messages_scroll, 1)

        input_row = QHBoxLayout()
        self.ai_chat_input = QTextEdit()
        self.ai_chat_input.setMaximumHeight(96)
        self.ai_chat_input.installEventFilter(self)
        self.ai_chat_input.viewport().installEventFilter(self)
        self.ai_send_button = QPushButton()
        self.ai_send_button.setObjectName("AIChatSendButton")
        self.ai_send_button.setFixedSize(QSize(64, 96))
        self.ai_send_button.clicked.connect(self.send_ai_chat_message)
        input_row.addWidget(self.ai_chat_input, 1)
        input_row.addWidget(self.ai_send_button)
        panel_layout.addLayout(input_row)

        root.addWidget(sidebar)
        root.addWidget(panel, 1)
        self.ai_current_session_id: Optional[int] = None
        self.ai_show_new_chat_placeholder = False
        self.ai_pending_session_id: Optional[int] = None
        self.ai_pending_user_message_id: Optional[int] = None
        self.ai_pending_assistant_message_id: Optional[int] = None
        self.ai_pending_actions: List[Dict[str, Any]] = []
        self.ai_chat_worker: Optional[AIChatWorker] = None
        self.ai_chat_worker_running = False
        self.ai_waiting_message_visible = False
        self.ai_streaming_message_card: Optional[AIMessageCard] = None
        self.ai_streaming_message_text = ""
        return page

    def retranslate_ai_chat_page(self) -> None:
        self.ai_chat_sessions_label.setText(self.tr("ai_chat_sessions"))
        self.ai_chat_title_label.setText(self.tr("ai_chat"))
        self.ai_new_chat_button.setText(self.tr("new_chat"))
        self.ai_delete_chat_button.setToolTip(self.tr("delete_chat"))
        self.ai_delete_chat_button.setAccessibleName(self.tr("delete_chat"))
        self.ai_delete_all_chats_button.setText(self.tr("delete_all_chats"))
        set_danger_button_icon(self.ai_delete_chat_button, "fa6s.trash", "Del", self.theme)
        self.ai_chat_input.setPlaceholderText(self.tr("ai_chat_input_placeholder"))
        self.ai_send_button.setText(self.tr("interrupt") if self.ai_chat_worker_running else self.tr("send"))

    def refresh_ai_chat_sessions(self) -> None:
        current_id = self.ai_current_session_id
        self.ai_chat_session_list.blockSignals(True)
        self.ai_chat_session_list.clear()
        sessions = self.db.get_ai_chat_sessions()
        if self.ai_show_new_chat_placeholder or not sessions:
            item = QListWidgetItem(self.tr("new_chat"))
            item.setData(Qt.ItemDataRole.UserRole, None)
            self._apply_list_item_color(item)
            self.ai_chat_session_list.addItem(item)
            if current_id is None:
                self.ai_chat_session_list.setCurrentItem(item)
        for session in sessions:
            title = session.get("title") or self.tr("new_chat")
            item = QListWidgetItem(f"#{session['id']} {title}")
            item.setData(Qt.ItemDataRole.UserRole, session["id"])
            self._apply_list_item_color(item)
            self.ai_chat_session_list.addItem(item)
            if current_id == session["id"]:
                self.ai_chat_session_list.setCurrentItem(item)
        self.ai_chat_session_list.blockSignals(False)
        if self.ai_chat_session_list.currentItem() is None and self.ai_chat_session_list.count():
            self.ai_chat_session_list.setCurrentRow(0)
        self.load_current_ai_chat_messages()

    def handle_ai_chat_session_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        value = current.data(Qt.ItemDataRole.UserRole) if current else None
        self.ai_current_session_id = int(value) if value is not None else None
        if value is not None:
            self.ai_show_new_chat_placeholder = False
        self.clear_ai_pending_actions()
        self.load_current_ai_chat_messages()
        self.restore_pending_ai_approval()

    def create_ai_chat_session_from_ui(self) -> None:
        self.ai_current_session_id = None
        self.ai_show_new_chat_placeholder = True
        self.refresh_ai_chat_sessions()
        self.focus_ai_chat_input()

    def delete_selected_ai_chat_session(self) -> None:
        if self.ai_current_session_id is None:
            return
        if QMessageBox.question(self, self.tr("delete_chat"), self.tr("delete_chat_confirm")) != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_ai_chat_session(self.ai_current_session_id)
        self.ai_current_session_id = None
        self.clear_ai_pending_actions()
        self.refresh_ai_chat_sessions()

    def delete_all_ai_chat_sessions_from_ui(self) -> None:
        if QMessageBox.question(self, self.tr("delete_all_chats"), self.tr("delete_all_chats_confirm")) != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_all_ai_chat_sessions()
        self.ai_current_session_id = None
        self.ai_show_new_chat_placeholder = True
        self.clear_ai_pending_actions()
        self.refresh_ai_chat_sessions()

    def undo_ai_operation_batch_from_message(self, batch_id: int) -> None:
        if self.ai_batch_is_undone(batch_id):
            self.load_current_ai_chat_messages()
            return
        if not QMessageBox.question(self, self.tr("undo_ai_batch"), self.tr("undo_ai_batch_confirm")) == QMessageBox.StandardButton.Yes:
            return
        if self.ai_batch_is_undone(batch_id):
            self.load_current_ai_chat_messages()
            return
        undone = self.db.undo_ai_operation_batch(batch_id)
        if not undone:
            QMessageBox.information(self, self.tr("undo_ai_batch"), self.tr("no_operation_was_undone"))
            self.load_current_ai_chat_messages()
            return
        self.refresh_all(force_detail=True)
        self.refresh_ai_chat_sessions()
        self.load_current_ai_chat_messages()
        self.show_history_operation_status(len(undone))

    def load_current_ai_chat_messages(self) -> None:
        if not hasattr(self, "ai_chat_messages_layout"):
            return
        self.clear_ai_message_widgets()
        if self.ai_current_session_id is None:
            self.add_ai_empty_message(self.tr("no_ai_chat_messages"))
            return
        added = False
        for message in self.db.get_ai_chat_messages(self.ai_current_session_id):
            role = str(message.get("role") or "")
            if role in {"tool", "system"}:
                continue
            label = self.tr(f"ai_role_{role}") if role in {"user", "assistant"} else role
            content = str(message.get("content") or "").strip()
            metadata = self.ai_message_metadata(message)
            if content or metadata.get("actions"):
                self.add_ai_message_widget(
                    role,
                    label,
                    content or self.tr("ai_actions_requested"),
                    str(message.get("created_at") or ""),
                    message=message,
                    metadata=metadata,
                )
                added = True
        if not added:
            self.add_ai_empty_message(self.tr("no_ai_chat_messages"))
        self.scroll_ai_messages_to_bottom()

    def clear_ai_message_widgets(self) -> None:
        self.ai_waiting_message_visible = False
        self.ai_streaming_message_card = None
        self.ai_streaming_message_text = ""
        while self.ai_chat_messages_layout.count():
            item = self.ai_chat_messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_ai_empty_message(self, text: str) -> None:
        frame = QFrame()
        frame.setObjectName("AIEmptyChatState")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        label = QLabel(text)
        label.setObjectName("AIEmptyChatText")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()
        self.ai_chat_messages_layout.addWidget(frame, 1)

    def add_ai_message_widget(
        self,
        role: str,
        label: str,
        content: str,
        meta: str = "",
        *,
        message: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        header_status: str = "",
    ) -> AIMessageCard:
        approval_handlers = {}
        batch_undo_handler = None
        batch_undone = False
        if (
            role == "assistant"
            and message is not None
            and metadata
            and metadata.get("approval_status") == "pending"
            and self.ai_current_session_id is not None
        ):
            user_message_id = self._previous_user_message_id(int(message["id"]))
            if user_message_id is not None:
                actions = [action for action in metadata.get("actions", []) if isinstance(action, dict)]
                approval_handlers = {
                    "allow_all": lambda _checked=False, sid=self.ai_current_session_id, uid=user_message_id, aid=int(message["id"]), acts=actions: self.start_ai_action_approval(
                        sid, uid, aid, acts, allow_follow_up_actions=True
                    ),
                    "allow_once": lambda _checked=False, sid=self.ai_current_session_id, uid=user_message_id, aid=int(message["id"]), acts=actions: self.start_ai_action_approval(
                        sid, uid, aid, acts, allow_follow_up_actions=False
                    ),
                    "reject": lambda _checked=False, sid=self.ai_current_session_id, uid=user_message_id, aid=int(message["id"]): self.start_ai_action_rejection(
                        sid, uid, aid
                    ),
                }
        elif role == "assistant" and metadata:
            batch_id = self.ai_batch_id_from_metadata(metadata)
            if batch_id is not None:
                batch_undone = self.ai_batch_is_undone(batch_id)
                if not batch_undone and self.ai_batch_can_undo(batch_id):
                    batch_undo_handler = lambda _checked=False, bid=batch_id: self.undo_ai_operation_batch_from_message(bid)
        card = AIMessageCard(
            role,
            label,
            content,
            meta,
            metadata=metadata,
            header_status=header_status,
            approval_handlers=approval_handlers,
            batch_undo_handler=batch_undo_handler,
            batch_undone=batch_undone,
            tool_labels=self.ai_tool_display_labels(),
            detail_labels=self.ai_action_detail_labels(),
            status_labels=self.ai_action_status_labels(),
            size_changed=self.update_ai_message_card_size,
            theme=self.theme,
        )
        viewport_width = self.ai_message_card_width()
        card.fit_to_width(viewport_width)
        self.ai_chat_messages_layout.addWidget(card)
        return card

    def ai_batch_id_from_metadata(self, metadata: Dict[str, Any]) -> Optional[int]:
        for result in metadata.get("action_results", []):
            if not isinstance(result, dict):
                continue
            value = result.get("ai_batch_id")
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    def ai_batch_can_undo(self, batch_id: int) -> bool:
        for batch in self.db.get_ai_operation_batches():
            if int(batch["id"]) == int(batch_id):
                return not bool(batch.get("undone_at"))
        return False

    def ai_batch_is_undone(self, batch_id: int) -> bool:
        if self.db.mark_ai_operation_batch_undone_if_history_undone(batch_id):
            return True
        for batch in self.db.get_ai_operation_batches():
            if int(batch["id"]) == int(batch_id):
                return bool(batch.get("undone_at"))
        return False

    def ai_tool_display_labels(self) -> Dict[str, str]:
        return {tool: self.tr(label_key) for tool, label_key in AI_TOOL_LABEL_KEYS.items()}

    def ai_action_detail_labels(self) -> Dict[str, str]:
        return {
            "tool": self.tr("ai_tool_internal_name"),
            "arguments": self.tr("ai_tool_arguments"),
            "status": self.tr("ai_tool_status"),
            "error": self.tr("ai_tool_error"),
            "result": self.tr("ai_tool_result"),
            "waiting": self.tr("ai_tool_waiting_result"),
            "operation": self.tr("action"),
            "allow_all": self.tr("allow_all"),
            "allow_once": self.tr("allow_once"),
            "reject_remaining": self.tr("reject_remaining"),
            "undo_batch": self.tr("undo_ai_batch"),
            "batch_undone": self.tr("ai_batch_status_undone"),
        }

    def ai_action_status_labels(self) -> Dict[str, str]:
        return {
            "pending": self.tr("ai_action_status_pending"),
            "running": self.tr("ai_action_status_running"),
            "ok": self.tr("ai_action_status_ok"),
            "error": self.tr("ai_action_status_error"),
            "rejected": self.tr("ai_action_status_rejected"),
            "skipped": self.tr("ai_action_status_skipped"),
            "approval_pending": self.tr("ai_approval_status_pending"),
            "approval_approved": self.tr("ai_approval_status_approved"),
            "approval_rejected": self.tr("ai_approval_status_rejected"),
            "approval_executed": self.tr("ai_approval_status_executed"),
            "approval_failed": self.tr("ai_approval_status_failed"),
            "approval_running": self.tr("ai_approval_status_running"),
        }

    def update_ai_message_card_size(self, card: AIMessageCard) -> None:
        card.fit_to_width(self.ai_message_card_width())
        self.ai_chat_messages_container.adjustSize()

    def ai_message_metadata(self, message: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = json.loads(message.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def ai_message_card_width(self) -> int:
        return max(260, self.ai_chat_messages_scroll.viewport().width() - 28)

    def resize_ai_message_cards(self) -> None:
        if not hasattr(self, "ai_chat_messages_layout"):
            return
        width = self.ai_message_card_width()
        for index in range(self.ai_chat_messages_layout.count()):
            item = self.ai_chat_messages_layout.itemAt(index)
            widget = item.widget()
            if isinstance(widget, AIMessageCard):
                widget.fit_to_width(width)

    def handle_ai_chat_viewport_event(self, watched: object, event: object) -> bool:
        if not hasattr(self, "ai_chat_messages_scroll"):
            return False
        if (
            hasattr(self, "ai_chat_input")
            and watched in (self.ai_chat_input, self.ai_chat_input.viewport())
            and event.type() == QEvent.Type.KeyPress
        ):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                self.send_ai_chat_message()
                return True
        if watched == self.ai_chat_messages_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.resize_ai_message_cards()
        return False

    def focus_ai_chat_input(self) -> None:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self.ai_chat_input.setFocus)

    def scroll_ai_messages_to_bottom(self) -> None:
        from PySide6.QtCore import QTimer

        def scroll() -> None:
            self.ai_chat_messages_container.adjustSize()
            bar = self.ai_chat_messages_scroll.verticalScrollBar()
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, scroll)

    def send_ai_chat_message(self) -> None:
        if self.ai_chat_worker_running:
            self.cancel_ai_chat_worker()
            return
        content = self.ai_chat_input.toPlainText().strip()
        if not content:
            return
        self.ai_chat_input.clear()
        self.append_pending_user_message(content)
        self.start_ai_chat_worker("send", content=content, session_id=self.ai_current_session_id)

    def append_pending_user_message(self, content: str) -> None:
        if self.ai_current_session_id is None:
            self.clear_ai_message_widgets()
        self.add_ai_message_widget(
            "user",
            self.tr("ai_role_user"),
            content,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.scroll_ai_messages_to_bottom()

    def append_ai_waiting_message(self) -> None:
        if self.ai_waiting_message_visible:
            return
        self.ai_streaming_message_card = self.add_ai_message_widget(
            "assistant",
            self.tr("ai_role_assistant"),
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            header_status=self.tr("ai_thinking"),
        )
        self.ai_streaming_message_text = ""
        self.ai_waiting_message_visible = True
        self.scroll_ai_messages_to_bottom()

    def append_ai_stream_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        if self.ai_streaming_message_card is None:
            self.append_ai_waiting_message()
        self.ai_streaming_message_text += chunk
        if self.ai_streaming_message_card is not None:
            self.ai_streaming_message_card.set_header_status(self.tr("ai_replying"))
            self.ai_streaming_message_card.set_content(self.ai_streaming_message_text)
            self.scroll_ai_messages_to_bottom()

    def reset_ai_stream_message(self) -> None:
        self.ai_streaming_message_text = ""
        if self.ai_streaming_message_card is None:
            self.append_ai_waiting_message()
            return
        self.ai_streaming_message_card.set_header_status(self.tr("ai_thinking"))
        self.ai_streaming_message_card.set_content("")
        self.scroll_ai_messages_to_bottom()

    def append_ai_error_message(self, message: str, *, session_id: Optional[int] = None) -> None:
        error_text = self.tr("ai_chat_failed", error=message)
        target_session_id = session_id if session_id is not None else self.ai_current_session_id
        if target_session_id is not None:
            self.db.add_ai_chat_message(target_session_id, "assistant", error_text)
            self.ai_current_session_id = target_session_id
            self.ai_show_new_chat_placeholder = False
            self.refresh_ai_chat_sessions()
            self.load_current_ai_chat_messages()
            return
        if self.ai_streaming_message_card is None:
            self.ai_streaming_message_card = self.add_ai_message_widget(
                "assistant",
                self.tr("ai_role_assistant"),
                error_text,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        else:
            self.ai_streaming_message_card.set_header_status("")
            self.ai_streaming_message_card.set_content(error_text)
        self.ai_waiting_message_visible = False
        self.ai_streaming_message_text = ""
        self.scroll_ai_messages_to_bottom()

    def cancel_ai_chat_worker(self) -> None:
        if self.ai_chat_worker is None:
            return
        self.ai_chat_worker.requestInterruption()
        self.ai_send_button.setEnabled(False)
        self.ai_send_button.setText(self.tr("interrupting"))

    def reject_remaining_ai_actions(self) -> None:
        if self.ai_pending_session_id is None or self.ai_pending_user_message_id is None:
            self.show_inline_message(self.ai_chat_status_label, self.tr("ai_no_pending_actions"), ALERT_WARN)
            return
        self.start_ai_chat_worker(
            "reject",
            session_id=self.ai_pending_session_id,
            user_message_id=self.ai_pending_user_message_id,
            assistant_message_id=self.ai_pending_assistant_message_id,
        )
        self.clear_ai_pending_actions()

    def start_ai_action_approval(
        self,
        session_id: int,
        user_message_id: int,
        assistant_message_id: int,
        actions: List[Dict[str, Any]],
        *,
        allow_follow_up_actions: bool,
    ) -> None:
        self.ai_pending_session_id = session_id
        self.ai_pending_user_message_id = user_message_id
        self.ai_pending_assistant_message_id = assistant_message_id
        self.ai_pending_actions = list(actions)
        self.start_pending_ai_approval(allow_follow_up_actions=allow_follow_up_actions)

    def start_ai_action_rejection(self, session_id: int, user_message_id: int, assistant_message_id: int) -> None:
        self.ai_pending_session_id = session_id
        self.ai_pending_user_message_id = user_message_id
        self.ai_pending_assistant_message_id = assistant_message_id
        self.reject_remaining_ai_actions()

    def start_pending_ai_approval(self, *, allow_follow_up_actions: bool) -> None:
        if self.ai_pending_session_id is None or self.ai_pending_user_message_id is None or not self.ai_pending_actions:
            self.show_inline_message(self.ai_chat_status_label, self.tr("ai_no_pending_actions"), ALERT_WARN)
            return
        if self.ai_pending_assistant_message_id is not None:
            actions, existing_results = self.current_ai_action_state(self.ai_pending_assistant_message_id, self.ai_pending_actions)
            self.db.update_ai_chat_message_metadata(
                self.ai_pending_assistant_message_id,
                {
                    "approval_status": "running",
                    "action_results": self.running_ai_action_results(actions, existing_results),
                },
            )
            self.load_current_ai_chat_messages()
        self.start_ai_chat_worker(
            "approve",
            session_id=self.ai_pending_session_id,
            user_message_id=self.ai_pending_user_message_id,
            assistant_message_id=self.ai_pending_assistant_message_id,
            actions=self.ai_pending_actions,
            allow_follow_up_actions=allow_follow_up_actions,
        )
        self.clear_ai_pending_actions()

    def current_ai_action_state(
        self,
        assistant_message_id: int,
        fallback_actions: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if self.ai_current_session_id is not None:
            for message in self.db.get_ai_chat_messages(self.ai_current_session_id):
                if int(message["id"]) == int(assistant_message_id):
                    metadata = self.ai_message_metadata(message)
                    actions = [action for action in metadata.get("actions", []) if isinstance(action, dict)]
                    results = [result for result in metadata.get("action_results", []) if isinstance(result, dict)]
                    return actions or list(fallback_actions), results
        return list(fallback_actions), []

    def running_ai_action_results(
        self,
        actions: List[Dict[str, Any]],
        existing_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        existing_results = existing_results or []
        results: List[Dict[str, Any]] = []
        running_set = False
        terminal_statuses = {"ok", "error", "rejected", "skipped"}
        for index, action in enumerate(actions):
            tool = str(action.get("tool") or action.get("name") or action.get("type") or "")
            if index < len(existing_results) and isinstance(existing_results[index], dict):
                previous = dict(existing_results[index])
                if str(previous.get("status") or "") in terminal_statuses:
                    results.append(previous)
                    continue
            status = "running" if not running_set else "pending"
            running_set = True
            results.append(
                {
                    "tool": tool,
                    "status": status,
                    "result_type": "message",
                    "result": "Running." if status == "running" else "Waiting for execution.",
                }
            )
        return results

    def start_ai_chat_worker(self, mode: str, **kwargs: Any) -> None:
        if self.ai_chat_worker_running:
            return
        self.set_ai_chat_busy(True)
        self.ai_chat_status_label.hide()
        self.append_ai_waiting_message()
        worker = AIChatWorker(self.db, mode, **kwargs)
        worker.result_ready.connect(self.handle_ai_chat_result)
        worker.progress_ready.connect(self.handle_ai_chat_progress)
        worker.chunk_ready.connect(self.append_ai_stream_chunk)
        worker.stream_reset_ready.connect(self.reset_ai_stream_message)
        worker.error_ready.connect(self.handle_ai_chat_error)
        worker.finished.connect(lambda worker_ref=worker: self.finish_ai_chat_worker(worker_ref))
        self.ai_chat_worker = worker
        self.ai_chat_worker_running = True
        worker.start()

    def finish_ai_chat_worker(self, worker: AIChatWorker) -> None:
        self.ai_chat_worker_running = False
        self.set_ai_chat_busy(False)
        if self.ai_chat_worker is worker:
            self.ai_chat_worker = None
        worker.deleteLater()

    def handle_ai_chat_progress(self) -> None:
        self.load_current_ai_chat_messages()
        self.append_ai_waiting_message()

    def handle_ai_chat_result(self, result: AIChatTurnResult) -> None:
        self.ai_waiting_message_visible = False
        self.ai_streaming_message_card = None
        self.ai_streaming_message_text = ""
        self.ai_current_session_id = result.session_id
        self.ai_show_new_chat_placeholder = False
        if result.status == "needs_approval":
            self.ai_pending_session_id = result.session_id
            self.ai_pending_user_message_id = result.user_message_id
            self.ai_pending_assistant_message_id = result.assistant_message_id
            self.ai_pending_actions = list(result.pending_actions)
        elif result.status == "tool_error":
            self.clear_ai_pending_actions()
            self.append_ai_error_message(result.error or "AI operation failed.", session_id=result.session_id)
            return
        elif result.status == "tool_round_limit":
            self.append_ai_error_message(result.error or self.tr("ai_tool_round_limit"), session_id=result.session_id)
            return
        elif result.status == "cancelled":
            self.clear_ai_pending_actions()
            self.append_ai_error_message(self.tr("ai_interrupted"), session_id=result.session_id)
            return
        elif result.status == "incomplete":
            self.clear_ai_pending_actions()
            self.append_ai_error_message(result.error or self.tr("ai_response_incomplete"), session_id=result.session_id)
            return
        else:
            self.clear_ai_pending_actions()
            self.refresh_all(force_detail=True)
        self.refresh_ai_chat_sessions()
        self.load_current_ai_chat_messages()

    def handle_ai_chat_error(self, message: str) -> None:
        self.ai_waiting_message_visible = False
        self.ai_streaming_message_text = ""
        self.append_ai_error_message(message)

    def set_ai_chat_busy(self, busy: bool) -> None:
        self.ai_send_button.setEnabled(True)
        self.ai_send_button.setText(self.tr("interrupt") if busy else self.tr("send"))
        self.ai_chat_input.setEnabled(not busy)

    def clear_ai_pending_actions(self) -> None:
        self.ai_pending_session_id = None
        self.ai_pending_user_message_id = None
        self.ai_pending_assistant_message_id = None
        self.ai_pending_actions = []

    def restore_pending_ai_approval(self) -> None:
        if self.ai_current_session_id is None:
            return
        pending = self.db.get_pending_ai_approval(self.ai_current_session_id)
        if not pending:
            return
        metadata = pending.get("metadata") or {}
        actions = [action for action in metadata.get("actions", []) if isinstance(action, dict)]
        user_message_id = self._previous_user_message_id(int(pending["id"]))
        if not actions or user_message_id is None:
            return
        self.ai_pending_session_id = self.ai_current_session_id
        self.ai_pending_user_message_id = user_message_id
        self.ai_pending_assistant_message_id = int(pending["id"])
        self.ai_pending_actions = actions

    def _previous_user_message_id(self, assistant_message_id: int) -> Optional[int]:
        if self.ai_current_session_id is None:
            return None
        previous_user_id: Optional[int] = None
        for message in self.db.get_ai_chat_messages(self.ai_current_session_id):
            if int(message["id"]) >= assistant_message_id:
                break
            if message.get("role") == "user":
                previous_user_id = int(message["id"])
        return previous_user_id
