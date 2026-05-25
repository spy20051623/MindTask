"""AI chat orchestration for MindTask."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .ai_client import OpenAICompatibleClient
from .ai_protocol import actions_from_fallback_text, actions_from_openai_message
from .ai_prompts import (
    assistant_visible_content,
    date_time_context_prompt,
    operation_sequence_approved_prompt,
    operation_sequence_executed_prompt,
    operation_sequence_failed_prompt,
    operation_sequence_rejected_prompt,
    operation_retry_prompt,
    system_prompt,
)
from .ai_tools import AIToolExecutor, ToolExecutionPolicy, WRITE_TOOLS, WRITE_TOOL_RESULT_SUCCESS, openai_tool_definitions
from .database import MindTaskDB


@dataclass(frozen=True)
class AIChatTurnResult:
    status: str
    session_id: int
    user_message_id: int
    assistant_message_id: Optional[int] = None
    content: str = ""
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""


class _VisibleStreamFilter:
    """Filter hidden thinking tags from streamed assistant text."""

    def __init__(self) -> None:
        self.buffer = ""
        self.hidden = False

    def feed(self, text: str) -> str:
        self.buffer += text
        output: List[str] = []
        while self.buffer:
            lower = self.buffer.lower()
            if self.hidden:
                end = self._hidden_end_index(lower)
                if end < 0:
                    self.buffer = self.buffer[-16:]
                    return "".join(output)
                close = self.buffer.find(">", end)
                if close < 0:
                    self.buffer = self.buffer[end:]
                    return "".join(output)
                self.buffer = self.buffer[close + 1 :]
                self.hidden = False
                continue

            start = self._hidden_start_index(lower)
            if start >= 0:
                output.append(self.buffer[:start])
                close = self.buffer.find(">", start)
                if close < 0:
                    self.buffer = self.buffer[start:]
                    return "".join(output)
                self.buffer = self.buffer[close + 1 :]
                self.hidden = True
                continue

            stray_end = self._hidden_end_index(lower)
            if stray_end >= 0:
                output.append(self.buffer[:stray_end])
                close = self.buffer.find(">", stray_end)
                if close < 0:
                    self.buffer = self.buffer[stray_end:]
                    return "".join(output)
                self.buffer = self.buffer[close + 1 :]
                continue

            flush_len = max(0, len(self.buffer) - 16)
            if flush_len <= 0:
                return "".join(output)
            output.append(self.buffer[:flush_len])
            self.buffer = self.buffer[flush_len:]
        return "".join(output)

    def finish(self) -> str:
        if self.hidden:
            self.buffer = ""
            return ""
        text = self.buffer
        self.buffer = ""
        return text

    def _hidden_start_index(self, lower: str) -> int:
        indexes = [index for index in (lower.find("<think"), lower.find("<thinking")) if index >= 0]
        return min(indexes) if indexes else -1

    def _hidden_end_index(self, lower: str) -> int:
        indexes = [index for index in (lower.find("</think"), lower.find("</thinking")) if index >= 0]
        return min(indexes) if indexes else -1


class AIChatService:
    """Persist chat turns, call the provider, and run approved MindTask tools."""

    def __init__(
        self,
        db: MindTaskDB,
        *,
        client: Optional[OpenAICompatibleClient] = None,
        policy: Optional[ToolExecutionPolicy] = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self.db = db
        self.client = client or OpenAICompatibleClient.from_config(db.config)
        self.policy = policy or ToolExecutionPolicy.from_config(db.config)
        self.max_tool_rounds = max(1, int(max_tool_rounds))

    def create_session(self, title: str = "") -> int:
        return self.db.create_ai_chat_session(title)

    def send_user_message(
        self,
        content: str,
        *,
        session_id: Optional[int] = None,
        model: str = "",
        approved: bool = False,
        high_risk_approved: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_stream_reset: Optional[Callable[[], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> AIChatTurnResult:
        text = content.strip()
        if not text:
            raise ValueError("Message content is required.")
        model_name = (model or self.db.config.ai_default_model).strip()
        self.client.ensure_ready(model_name)

        if session_id is None:
            session_id = self.create_session(self._session_title_from_message(text))
        self._ensure_session_system_prompt(session_id)
        self.db.add_ai_chat_message(
            session_id,
            "system",
            date_time_context_prompt(),
            metadata={"kind": "runtime_context"},
        )
        user_message_id = self.db.add_ai_chat_message(session_id, "user", text)
        result = self._continue_session(
            session_id=session_id,
            user_message_id=user_message_id,
            model=model_name,
            approved=approved,
            high_risk_approved=high_risk_approved,
            on_chunk=on_chunk,
            on_stream_reset=on_stream_reset,
            should_cancel=should_cancel,
        )
        return result

    def continue_after_approval(
        self,
        *,
        session_id: int,
        user_message_id: int,
        actions: List[Dict[str, Any]],
        assistant_message_id: Optional[int] = None,
        model: str = "",
        allow_follow_up_actions: bool = False,
        after_execution: Optional[Callable[[], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_stream_reset: Optional[Callable[[], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> AIChatTurnResult:
        model_name = (model or self.db.config.ai_default_model).strip()
        self.client.ensure_ready(model_name)
        self._ensure_session_system_prompt(session_id)
        full_actions, existing_results = self._approval_state(session_id, assistant_message_id, actions)
        pending_indices = self._pending_action_indices(full_actions, existing_results)
        if not pending_indices:
            return AIChatTurnResult(
                status="needs_approval",
                session_id=session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                pending_actions=[],
            )
        selected_indices = pending_indices if allow_follow_up_actions else pending_indices[:1]
        selected_actions = [full_actions[index] for index in selected_indices]
        executor = AIToolExecutor(self.db, self.policy)
        execution = executor.execute_actions(
            selected_actions,
            session_id=session_id,
            user_message_id=user_message_id,
            model=model_name,
            approved=True,
            high_risk_approved=True,
        )
        merged_results = self._merge_action_results(
            full_actions,
            existing_results,
            selected_indices,
            execution,
        )
        remaining_indices = self._pending_action_indices(full_actions, merged_results)
        if assistant_message_id is not None:
            self.db.update_ai_chat_message_metadata(
                assistant_message_id,
                {
                    "approval_status": self._approval_status_from_results(merged_results),
                    "action_results": merged_results,
                },
            )
        if execution.get("status") == "needs_approval":
            return AIChatTurnResult(
                status="needs_approval",
                session_id=session_id,
                user_message_id=user_message_id,
                pending_actions=self._pending_actions_from_execution(execution),
            )
        if execution.get("status") == "error":
            selected_action_results = self._action_results_from_execution(selected_actions, execution)
            self.db.add_ai_chat_message(
                session_id,
                "system",
                self._failed_operation_prompt(
                    full_actions,
                    execution,
                    selected_indices=selected_indices,
                    action_results=selected_action_results,
                ),
                metadata={"kind": "interaction"},
            )
            if after_execution is not None:
                after_execution()
            result = self._continue_session(
                session_id=session_id,
                user_message_id=user_message_id,
                model=model_name,
                approved=False,
                high_risk_approved=False,
                on_chunk=on_chunk,
                on_stream_reset=on_stream_reset,
                should_cancel=should_cancel,
            )
            if result.tool_results:
                return result
            return AIChatTurnResult(
                status=result.status,
                session_id=result.session_id,
                user_message_id=result.user_message_id,
                assistant_message_id=result.assistant_message_id,
                content=result.content,
                tool_results=[execution],
                pending_actions=result.pending_actions,
                error=result.error,
            )
        selected_action_results = self._action_results_from_execution(selected_actions, execution)
        if remaining_indices:
            if after_execution is not None:
                after_execution()
            return AIChatTurnResult(
                status="needs_approval",
                session_id=session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                tool_results=[execution],
                pending_actions=[full_actions[index] for index in remaining_indices],
            )
        self.db.add_ai_chat_message(
            session_id,
            "system",
            operation_sequence_executed_prompt(selected_action_results, approved_by_user=True),
            metadata={"kind": "interaction"},
        )
        if after_execution is not None:
            after_execution()
        result = self._continue_session(
            session_id=session_id,
            user_message_id=user_message_id,
            model=model_name,
            approved=allow_follow_up_actions,
            high_risk_approved=allow_follow_up_actions,
            on_chunk=on_chunk,
            on_stream_reset=on_stream_reset,
            should_cancel=should_cancel,
        )
        if result.tool_results:
            return result
        return AIChatTurnResult(
            status=result.status,
            session_id=result.session_id,
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
            content=result.content,
            tool_results=[execution],
            pending_actions=result.pending_actions,
            error=result.error,
        )

    def reject_pending_actions(
        self,
        *,
        session_id: int,
        user_message_id: int,
        assistant_message_id: Optional[int] = None,
        model: str = "",
        after_execution: Optional[Callable[[], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_stream_reset: Optional[Callable[[], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> AIChatTurnResult:
        model_name = (model or self.db.config.ai_default_model).strip()
        self.client.ensure_ready(model_name)
        self._ensure_session_system_prompt(session_id)
        rejected_index = 1
        if assistant_message_id is not None:
            actions, existing_results = self._approval_state(session_id, assistant_message_id, [])
            pending_indices = self._pending_action_indices(actions, existing_results)
            rejected_index = (pending_indices[0] + 1) if pending_indices else 1
            merged_results = self._rejected_action_results(actions, existing_results, pending_indices)
            self.db.update_ai_chat_message_metadata(
                assistant_message_id,
                {
                    "approval_status": "rejected",
                    "action_results": merged_results,
                },
            )
        self.db.add_ai_chat_message(
            session_id,
            "system",
            operation_sequence_rejected_prompt(rejected_index),
            metadata={"kind": "interaction"},
        )
        if after_execution is not None:
            after_execution()
        return self._continue_session(
            session_id=session_id,
            user_message_id=user_message_id,
            model=model_name,
            approved=False,
            high_risk_approved=False,
            on_chunk=on_chunk,
            on_stream_reset=on_stream_reset,
            should_cancel=should_cancel,
        )

    def _continue_session(
        self,
        *,
        session_id: int,
        user_message_id: int,
        model: str,
        approved: bool,
        high_risk_approved: bool,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_stream_reset: Optional[Callable[[], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> AIChatTurnResult:
        all_tool_results: List[Dict[str, Any]] = []
        last_assistant_message_id: Optional[int] = None
        last_content = ""
        retry_incomplete_once = True

        for _round in range(self.max_tool_rounds):
            if should_cancel is not None and should_cancel():
                return AIChatTurnResult(
                    status="cancelled",
                    session_id=session_id,
                    user_message_id=user_message_id,
                    assistant_message_id=last_assistant_message_id,
                    content=last_content,
                    tool_results=all_tool_results,
                    error="AI request was interrupted.",
                )
            assistant = self._chat_completion(
                model=model,
                messages=self._provider_messages(session_id),
                tools=openai_tool_definitions(),
                on_chunk=on_chunk,
                should_cancel=should_cancel,
            )
            if assistant.get("_cancelled"):
                return AIChatTurnResult(
                    status="cancelled",
                    session_id=session_id,
                    user_message_id=user_message_id,
                    assistant_message_id=last_assistant_message_id,
                    content=last_content,
                    tool_results=all_tool_results,
                    error="AI request was interrupted.",
                )
            if assistant.get("_incomplete"):
                return AIChatTurnResult(
                    status="incomplete",
                    session_id=session_id,
                    user_message_id=user_message_id,
                    assistant_message_id=last_assistant_message_id,
                    content=last_content,
                    tool_results=all_tool_results,
                    error=str(assistant.get("_incomplete_reason") or "AI response was cut off before it finished."),
                )
            last_content = assistant_visible_content(assistant)
            actions = actions_from_openai_message(assistant)
            if not actions:
                actions = actions_from_fallback_text(last_content)
            if not actions and self._looks_like_truncated_reply(last_content) and retry_incomplete_once:
                retry_incomplete_once = False
                if on_stream_reset is not None:
                    on_stream_reset()
                self.db.add_ai_chat_message(
                    session_id,
                    "system",
                    operation_retry_prompt(),
                    metadata={"kind": "interaction"},
                )
                continue

            last_assistant_message_id = self.db.add_ai_chat_message(
                session_id,
                "assistant",
                last_content,
                metadata=self._assistant_metadata(assistant, actions),
            )
            if not actions:
                return AIChatTurnResult(
                    status="ok",
                    session_id=session_id,
                    user_message_id=user_message_id,
                    assistant_message_id=last_assistant_message_id,
                    content=last_content,
                    tool_results=all_tool_results,
                )

            executor = AIToolExecutor(self.db, self.policy)
            execution = executor.execute_actions(
                actions,
                session_id=session_id,
                user_message_id=user_message_id,
                model=model,
                approved=approved,
                high_risk_approved=high_risk_approved,
            )
            if execution.get("status") == "needs_approval":
                self.db.update_ai_chat_message_metadata(
                    last_assistant_message_id,
                    {"approval_status": "pending"},
                )
                return AIChatTurnResult(
                    status="needs_approval",
                    session_id=session_id,
                    user_message_id=user_message_id,
                    assistant_message_id=last_assistant_message_id,
                    content=last_content,
                    tool_results=all_tool_results,
                    pending_actions=self._pending_actions_from_execution(execution),
                )

            all_tool_results.append(execution)
            action_results = self._action_results_from_execution(actions, execution)
            self.db.update_ai_chat_message_metadata(
                last_assistant_message_id,
                {
                    "approval_status": "failed" if execution.get("status") == "error" else "executed",
                    "action_results": action_results,
                },
            )
            if execution.get("status") == "error":
                self.db.add_ai_chat_message(
                    session_id,
                    "system",
                    self._failed_operation_prompt(actions, execution, action_results=action_results),
                    metadata={"kind": "interaction"},
                )
                continue
            self.db.add_ai_chat_message(
                session_id,
                "system",
                operation_sequence_executed_prompt(action_results),
                metadata={"kind": "interaction"},
            )

        return AIChatTurnResult(
            status="tool_round_limit",
            session_id=session_id,
            user_message_id=user_message_id,
            assistant_message_id=last_assistant_message_id,
            content=last_content,
            tool_results=all_tool_results,
            error="AI tool round limit reached.",
        )

    def _chat_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        on_chunk: Optional[Callable[[str], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        if on_chunk is None:
            return self.client.chat_completion(model=model, messages=messages, tools=tools)
        return self._stream_chat_completion(
            model=model,
            messages=messages,
            tools=tools,
            on_chunk=on_chunk,
            should_cancel=should_cancel,
        )

    def _stream_chat_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        on_chunk: Callable[[str], None],
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        content_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        visible_filter = _VisibleStreamFilter()
        done_seen = False
        finish_reason = ""
        for event in self._client_stream_events(model, messages, tools, should_cancel):
            if event.get("_mindtask_done"):
                done_seen = True
                break
            choices = event.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            reason = choices[0].get("finish_reason")
            if isinstance(reason, str) and reason:
                finish_reason = reason
            delta = choices[0].get("delta") or {}
            if not isinstance(delta, dict):
                continue
            content = delta.get("content")
            if isinstance(content, str) and content:
                content_parts.append(content)
                visible = visible_filter.feed(content)
                if visible:
                    on_chunk(visible)
            if delta.get("reasoning_content") or delta.get("reasoning"):
                continue
            self._merge_stream_tool_calls(tool_calls, delta.get("tool_calls"))
            if should_cancel is not None and should_cancel():
                tail = visible_filter.finish()
                if tail:
                    on_chunk(tail)
                return {"content": "".join(content_parts), "_cancelled": True}
        tail = visible_filter.finish()
        if tail:
            on_chunk(tail)
        message: Dict[str, Any] = {"content": "".join(content_parts)}
        if should_cancel is not None and should_cancel():
            message["_cancelled"] = True
        if finish_reason in {"length", "content_filter"}:
            message["_incomplete"] = True
            message["_incomplete_reason"] = (
                "AI response was cut off because it reached the provider limit."
                if finish_reason == "length"
                else "AI response was stopped by the provider content filter."
            )
        elif not done_seen and finish_reason not in {"stop", "tool_calls"}:
            message["_incomplete"] = True
            message["_incomplete_reason"] = "AI response stream ended before completion."
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message

    def _looks_like_truncated_reply(self, content: str) -> bool:
        text = content.strip()
        if not text:
            return False
        lower = text.lower()
        if lower in {"if", "now", "then", "so", "but", "and"}:
            return True
        if text in {"现在", "如果", "然后", "所以", "但是", "并且", "接下来"}:
            return True
        if len(text) <= 3:
            return True
        incomplete_endings = (
            "if",
            "then",
            "because",
            "so",
            "but",
            "and",
            "现在",
            "如果",
            "然后",
            "因为",
            "所以",
            "但是",
            "接下来",
        )
        return any(lower.endswith(ending) for ending in incomplete_endings)

    def _client_stream_events(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        should_cancel: Optional[Callable[[], bool]],
    ):
        try:
            return self.client.chat_completion_stream(
                model=model,
                messages=messages,
                tools=tools,
                should_cancel=should_cancel,
            )
        except TypeError:
            return self.client.chat_completion_stream(model=model, messages=messages, tools=tools)

    def _ensure_session_system_prompt(self, session_id: int) -> None:
        for row in self.db.get_ai_chat_messages(session_id):
            if row.get("role") != "system":
                continue
            metadata = self._message_metadata(row)
            if metadata.get("kind") == "system_prompt" or (row.get("content") or "") == system_prompt():
                return
        self.db.add_ai_chat_message(
            session_id,
            "system",
            system_prompt(),
            metadata={"kind": "system_prompt"},
        )

    def _merge_stream_tool_calls(self, tool_calls: List[Dict[str, Any]], delta_calls: Any) -> None:
        if not isinstance(delta_calls, list):
            return
        for delta_call in delta_calls:
            if not isinstance(delta_call, dict):
                continue
            index = int(delta_call.get("index") or 0)
            while len(tool_calls) <= index:
                tool_calls.append({"function": {"name": "", "arguments": ""}})
            target = tool_calls[index]
            if delta_call.get("id"):
                target["id"] = str(delta_call["id"])
            if delta_call.get("type"):
                target["type"] = str(delta_call["type"])
            function = delta_call.get("function")
            if isinstance(function, dict):
                target_function = target.setdefault("function", {"name": "", "arguments": ""})
                if function.get("name"):
                    target_function["name"] = str(target_function.get("name") or "") + str(function["name"])
                if function.get("arguments"):
                    target_function["arguments"] = str(target_function.get("arguments") or "") + str(function["arguments"])

    def _provider_messages(self, session_id: int) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        for row in self.db.get_ai_chat_messages(session_id):
            role = row["role"]
            if role not in {"user", "assistant", "tool", "system"}:
                continue
            content = row.get("content") or ""
            metadata = self._message_metadata(row)
            if role == "user":
                message: Dict[str, Any] = {"role": "user", "content": content}
            elif role == "assistant":
                message = {"role": "assistant", "content": content}
            elif role == "tool":
                message = {"role": "system", "content": "Legacy MindTask tool result:\n" + content}
            else:
                message = {"role": "system", "content": self._provider_system_content(content)}
            messages.append(message)
        return messages

    def _approval_state(
        self,
        session_id: int,
        assistant_message_id: Optional[int],
        fallback_actions: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if assistant_message_id is not None:
            for message in self.db.get_ai_chat_messages(session_id):
                if int(message["id"]) == int(assistant_message_id):
                    metadata = self._message_metadata(message)
                    actions = [action for action in metadata.get("actions", []) if isinstance(action, dict)]
                    results = [result for result in metadata.get("action_results", []) if isinstance(result, dict)]
                    if actions:
                        return actions, results
                    break
        return list(fallback_actions), []

    def _pending_action_indices(
        self,
        actions: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
    ) -> List[int]:
        terminal_statuses = {"ok", "error", "rejected", "skipped"}
        pending: List[int] = []
        for index, _action in enumerate(actions):
            status = ""
            if index < len(results) and isinstance(results[index], dict):
                status = str(results[index].get("status") or "")
            if status not in terminal_statuses:
                pending.append(index)
        return pending

    def _merge_action_results(
        self,
        actions: List[Dict[str, Any]],
        existing_results: List[Dict[str, Any]],
        selected_indices: List[int],
        execution: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        merged = self._normalize_action_results(actions, existing_results)
        selected_results = self._action_results_from_execution(
            [actions[index] for index in selected_indices],
            execution,
        )
        failed_absolute_index: Optional[int] = None
        for offset, action_index in enumerate(selected_indices):
            if offset >= len(selected_results):
                break
            merged[action_index] = selected_results[offset]
            if selected_results[offset].get("status") == "error":
                failed_absolute_index = action_index
                break
        if failed_absolute_index is not None:
            for index in range(failed_absolute_index + 1, len(actions)):
                if str(merged[index].get("status") or "") not in {"ok", "error", "rejected", "skipped"}:
                    merged[index] = self._skipped_action_result(actions[index], "Skipped because a previous operation failed.")
        return merged

    def _normalize_action_results(
        self,
        actions: List[Dict[str, Any]],
        existing_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for index, action in enumerate(actions):
            if index < len(existing_results) and isinstance(existing_results[index], dict):
                normalized.append(dict(existing_results[index]))
            else:
                normalized.append(self._pending_action_result(action))
        return normalized

    def _pending_action_result(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "tool": str(action.get("tool") or action.get("name") or action.get("type") or ""),
            "status": "pending",
            "result_type": "message",
            "result": "Waiting for execution.",
        }

    def _skipped_action_result(self, action: Dict[str, Any], reason: str) -> Dict[str, Any]:
        return {
            "tool": str(action.get("tool") or action.get("name") or action.get("type") or ""),
            "status": "skipped",
            "result_type": "message",
            "result": reason,
        }

    def _approval_status_from_results(self, results: List[Dict[str, Any]]) -> str:
        statuses = [str(result.get("status") or "") for result in results]
        if any(status == "error" for status in statuses):
            return "failed"
        if any(status == "rejected" for status in statuses):
            return "rejected"
        if any(status not in {"ok", "skipped"} for status in statuses):
            return "pending"
        return "approved"

    def _failed_operation_prompt(
        self,
        actions: List[Dict[str, Any]],
        execution: Dict[str, Any],
        *,
        selected_indices: Optional[List[int]] = None,
        action_results: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        results = execution.get("results") or []
        failed_index = 1
        for index, result in enumerate(results, start=1):
            if isinstance(result, dict) and result.get("status") == "error":
                failed_index = (selected_indices[index - 1] + 1) if selected_indices and index - 1 < len(selected_indices) else index
                break
        else:
            failed_index = min(max(len(results), 1), max(len(actions), 1))
        return operation_sequence_failed_prompt(failed_index, action_results)

    def _provider_system_content(self, content: str) -> str:
        if content.startswith("System event: The user approved all requested MindTask operations."):
            return operation_sequence_approved_prompt()
        if content.startswith("System event: The user rejected operation #"):
            marker = "operation #"
            try:
                operation_index = int(content.split(marker, 1)[1].split(".", 1)[0])
            except (IndexError, ValueError):
                operation_index = 1
            return operation_sequence_rejected_prompt(operation_index)
        if content.startswith("System event: MindTask stopped the requested operation sequence"):
            return operation_sequence_failed_prompt(1)
        return content

    def _session_title_from_message(self, text: str) -> str:
        return text[:40]

    def _message_metadata(self, row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = json.loads(row.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _pending_actions_from_execution(self, execution: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions = execution.get("actions")
        if isinstance(actions, list):
            return [action for action in actions if isinstance(action, dict)]
        action = execution.get("action")
        return [action] if isinstance(action, dict) else []

    def _assistant_metadata(self, assistant: Dict[str, Any], actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "tool_calls": assistant.get("tool_calls") or [],
            "actions": actions,
        }
        if actions:
            metadata["approval_status"] = "executed"
        return metadata

    def _action_results_from_execution(
        self,
        actions: List[Dict[str, Any]],
        execution: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        results = execution.get("results") or []
        action_results: List[Dict[str, Any]] = []
        failed_seen = False
        for index, action in enumerate(actions):
            result = results[index] if index < len(results) and isinstance(results[index], dict) else {}
            status = str(result.get("status") or execution.get("status") or "")
            tool = str(action.get("tool") or action.get("name") or action.get("type") or result.get("tool") or "")
            action_result: Dict[str, Any] = {
                "tool": tool,
                "status": status,
            }
            if failed_seen or (execution.get("status") == "error" and index >= len(results)):
                action_result["status"] = "skipped"
                action_result["result_type"] = "message"
                action_result["result"] = "Skipped because a previous operation failed."
                if execution.get("ai_batch_id") is not None:
                    action_result["ai_batch_id"] = execution["ai_batch_id"]
                action_results.append(action_result)
                continue
            error = str(result.get("error") or execution.get("error") or "")
            if status == "ok":
                if tool in WRITE_TOOLS:
                    action_result["result_type"] = "message"
                    action_result["result"] = WRITE_TOOL_RESULT_SUCCESS.get(tool, "Operation completed successfully.")
                else:
                    action_result["result_type"] = "json"
                    action_result["result"] = result.get("result")
            elif error:
                action_result["status"] = "error"
                action_result["error"] = error
                action_result["result_type"] = "error"
                action_result["result"] = error
                failed_seen = True
            else:
                action_result["result_type"] = "message"
                action_result["result"] = status or "No result returned."
            if execution.get("ai_batch_id") is not None:
                action_result["ai_batch_id"] = execution["ai_batch_id"]
            action_results.append(action_result)
        return action_results

    def _rejected_action_results(
        self,
        actions: List[Dict[str, Any]],
        existing_results: Optional[List[Dict[str, Any]]] = None,
        pending_indices: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        existing_results = existing_results or []
        pending_indices = pending_indices if pending_indices is not None else self._pending_action_indices(actions, existing_results)
        action_results = self._normalize_action_results(actions, existing_results)
        if not pending_indices:
            return action_results
        rejected_index = pending_indices[0]
        action_results[rejected_index] = {
            "tool": str(actions[rejected_index].get("tool") or actions[rejected_index].get("name") or actions[rejected_index].get("type") or ""),
            "status": "rejected",
            "result_type": "message",
            "result": "User rejected this operation.",
        }
        for index in pending_indices[1:]:
            action_results[index] = self._skipped_action_result(actions[index], "Skipped because a previous operation was rejected.")
        return action_results
