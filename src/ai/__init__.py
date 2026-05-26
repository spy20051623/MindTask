"""AI package exports for MindTask."""

from .chat import AIChatService, AIChatTurnResult
from .client import AIClientError, AIConfigurationError, AIModelInfo, OpenAICompatibleClient
from .prompts import SYSTEM_PROMPT, assistant_visible_content, date_time_context_prompt, system_prompt
from .protocol import (
    ACTIONS_JSON_END,
    ACTIONS_JSON_START,
    AIProtocolError,
    actions_from_fallback_text,
    actions_from_openai_message,
    actions_from_openai_tool_calls,
)
from .tools import AIToolError, AIToolExecutor, ToolExecutionPolicy, openai_tool_definitions

__all__ = [
    "ACTIONS_JSON_END",
    "ACTIONS_JSON_START",
    "AIChatService",
    "AIChatTurnResult",
    "AIClientError",
    "AIConfigurationError",
    "AIModelInfo",
    "AIProtocolError",
    "AIToolError",
    "AIToolExecutor",
    "OpenAICompatibleClient",
    "SYSTEM_PROMPT",
    "ToolExecutionPolicy",
    "actions_from_fallback_text",
    "actions_from_openai_message",
    "actions_from_openai_tool_calls",
    "assistant_visible_content",
    "date_time_context_prompt",
    "openai_tool_definitions",
    "system_prompt",
]
