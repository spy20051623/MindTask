"""OpenAI-compatible HTTP client for MindTask AI features."""

from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urljoin, urlparse

from .config import MindTaskConfig


class AIClientError(RuntimeError):
    """Raised when an AI provider request fails."""


class AIConfigurationError(AIClientError):
    """Raised when AI settings are incomplete."""


@dataclass(frozen=True)
class AIModelInfo:
    id: str
    name: str = ""


class OpenAICompatibleClient:
    """Small OpenAI-compatible client using the standard library only."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        request_timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/" if base_url.strip() else ""
        self.api_key = api_key.strip()
        self.request_timeout_seconds = max(0, int(request_timeout_seconds))

    @classmethod
    def from_config(cls, config: MindTaskConfig) -> "OpenAICompatibleClient":
        return cls(
            config.ai_base_url,
            config.ai_api_key,
            request_timeout_seconds=config.ai_request_timeout_seconds,
        )

    def ensure_ready(self, model: str = "") -> None:
        if not self.base_url:
            raise AIConfigurationError("AI base URL is not configured.")
        if not self.api_key:
            raise AIConfigurationError("AI API key is not configured.")
        if model is not None and not str(model).strip():
            raise AIConfigurationError("AI model is not configured.")

    def chat_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        self.ensure_ready(model)
        payload: Dict[str, Any] = {
            "model": model.strip(),
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        data = self._request_json("POST", self._join_base("chat/completions"), payload)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIClientError("AI response did not include choices.")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise AIClientError("AI response did not include a message.")
        return message

    def chat_completion_stream(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Iterator[Dict[str, Any]]:
        self.ensure_ready(model)
        payload: Dict[str, Any] = {
            "model": model.strip(),
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        yield from self._request_sse("POST", self._join_base("chat/completions"), payload, should_cancel=should_cancel)

    def list_models(self, endpoint: str = "") -> List[AIModelInfo]:
        self.ensure_ready(model=None)
        url = endpoint.strip() or self._join_base("models")
        data = self._request_json("GET", url, None)
        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise AIClientError("Model list response did not include a data list.")
        models: List[AIModelInfo] = []
        for item in items:
            if isinstance(item, str):
                model_id = item.strip()
                name = ""
            elif isinstance(item, dict):
                model_id = str(item.get("id") or item.get("name") or "").strip()
                name = str(item.get("name") or "").strip()
            else:
                continue
            if model_id:
                models.append(AIModelInfo(model_id, name))
        return models

    def _join_base(self, suffix: str) -> str:
        if not self.base_url:
            raise AIConfigurationError("AI base URL is not configured.")
        return urljoin(self.base_url, suffix)

    def _request_json(self, method: str, url: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AIClientError("AI endpoint URL is invalid.")

        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        timeout = self.request_timeout_seconds or None
        connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        conn: Optional[http.client.HTTPConnection] = None
        try:
            conn = connection_cls(parsed.netloc, timeout=timeout)
            conn.request(method.upper(), path, body=body, headers=headers)
            response = conn.getresponse()
            self._disable_response_timeout(response)
            raw = response.read()
        except OSError as exc:
            raise AIClientError(f"AI request failed: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        text = raw.decode("utf-8", errors="replace")
        if response.status < 200 or response.status >= 300:
            raise AIClientError(f"AI request failed with HTTP {response.status}: {text[:500]}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIClientError("AI response was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise AIClientError("AI response JSON must be an object.")
        return data

    def _request_sse(
        self,
        method: str,
        url: str,
        payload: Dict[str, Any],
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Iterator[Dict[str, Any]]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AIClientError("AI endpoint URL is invalid.")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = self.request_timeout_seconds or None
        connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        conn: Optional[http.client.HTTPConnection] = None
        try:
            conn = connection_cls(parsed.netloc, timeout=timeout)
            conn.request(method.upper(), path, body=body, headers=headers)
            response = conn.getresponse()
            self._disable_response_timeout(response)
            if response.status < 200 or response.status >= 300:
                raw = response.read()
                text = raw.decode("utf-8", errors="replace")
                raise AIClientError(f"AI request failed with HTTP {response.status}: {text[:500]}")
            for data in self._iter_sse_data(response, should_cancel=should_cancel):
                if should_cancel is not None and should_cancel():
                    break
                if data == "[DONE]":
                    yield {"_mindtask_done": True}
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise AIClientError("AI stream response included invalid JSON.") from exc
                if isinstance(event, dict):
                    yield event
        except OSError as exc:
            raise AIClientError(f"AI request failed: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _iter_sse_data(
        self,
        response: http.client.HTTPResponse,
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Iterator[str]:
        data_lines: List[str] = []
        while True:
            if should_cancel is not None and should_cancel():
                break
            raw_line = response.readline()
            if raw_line == b"":
                if data_lines:
                    yield "\n".join(data_lines).strip()
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                if data_lines:
                    yield "\n".join(data_lines).strip()
                    data_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

    def _disable_response_timeout(self, response: http.client.HTTPResponse) -> None:
        """Keep the configured timeout scoped to the provider response starting."""
        try:
            sock = response.fp.raw._sock
            sock.settimeout(None)
        except Exception:
            pass
