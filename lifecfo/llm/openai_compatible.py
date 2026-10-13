"""Client for the OpenAI-compatible chat API that Gemini, Groq, and Ollama all expose.

Uses only the standard library, so no provider SDK is needed. Errors are
mapped to `LLMError` kinds; rate limits and brief outages are retried a small
number of times and then reported, never worked around by changing provider.
"""

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from lifecfo.llm.base import (
    ChatMessage,
    LLMClient,
    LLMError,
    LLMErrorKind,
    LLMResponse,
    ToolCall,
    ToolSpec,
)
from lifecfo.llm.config import LLMSettings

# (url, headers, body, timeout) -> (status, headers, text)
Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, dict[str, str], str]]

MAX_RETRY_WAIT_SECONDS = 8.0
_RETRY_HINT = re.compile(r"retry in ([0-9.]+)\s*s", re.IGNORECASE)


def _urllib_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read().decode("utf-8", "replace")


def _message_payload(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        payload["tool_calls"] = [
            {**call.extra, "id": call.id, "type": "function",
             "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    return payload


class OpenAICompatibleClient:
    def __init__(
        self,
        settings: LLMSettings,
        transport: Transport = _urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = settings.provider
        self.model = settings.model
        self._settings = settings
        self._transport = transport
        self._sleep = sleep

    def _error(self, kind: LLMErrorKind, detail: str = "") -> LLMError:
        return LLMError(kind, self.provider, detail[:200])

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        settings = self._settings
        if settings.problem or not settings.base_url:
            raise self._error(LLMErrorKind.NOT_CONFIGURED, settings.problem or "")

        body: dict[str, Any] = {
            "model": settings.model,
            "messages": [_message_payload(m) for m in messages],
            "temperature": 0,
        }
        if tools:
            body["tools"] = [
                {"type": "function",
                 "function": {"name": t.name, "description": t.description,
                              "parameters": t.parameters}}
                for t in tools
            ]
            body["tool_choice"] = "auto"
        # Some providers (Groq, behind Cloudflare) reject the default urllib user agent.
        headers = {"Content-Type": "application/json", "User-Agent": "lifecfo-ai/0.1"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"

        last: LLMError | None = None
        for attempt in range(settings.max_retries + 1):
            try:
                status, response_headers, text = self._transport(
                    f"{settings.base_url}/chat/completions", headers,
                    json.dumps(body).encode("utf-8"), settings.timeout_seconds,
                )
            except (OSError, TimeoutError) as error:
                last = self._error(LLMErrorKind.UNAVAILABLE, type(error).__name__)
                status, response_headers, text = 0, {}, ""
            else:
                if status == 200:
                    return self._parse(text)
                last = self._classify(status, text)

            retryable = last.kind in (LLMErrorKind.RATE_LIMITED, LLMErrorKind.UNAVAILABLE)
            if not retryable or attempt == settings.max_retries:
                break
            wait = self._retry_wait(response_headers, text, attempt)
            if wait is None:
                break  # the provider asked for a long wait; retrying would only burn quota
            self._sleep(wait)
        assert last is not None
        raise last

    @staticmethod
    def _retry_wait(headers: dict[str, str], text: str, attempt: int) -> float | None:
        """Seconds to wait before retrying, or None when the provider wants a long pause."""
        asked: float | None = None
        retry_after = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
        hinted = _RETRY_HINT.search(text)
        try:
            if retry_after is not None:
                asked = float(retry_after)
            elif hinted:
                asked = float(hinted.group(1))
        except ValueError:
            asked = None
        if asked is None:
            return min(2.0**attempt, MAX_RETRY_WAIT_SECONDS)
        return max(asked, 0.0) if asked <= MAX_RETRY_WAIT_SECONDS else None

    def _classify(self, status: int, text: str) -> LLMError:
        lowered = text.lower()
        if status in (401, 403):
            return self._error(LLMErrorKind.AUTH, f"HTTP {status}")
        if status == 404:
            return self._error(LLMErrorKind.MODEL_NOT_FOUND, f"HTTP {status}")
        if status == 429:
            # Gemini words a per-minute limit as "quota exceeded ... please retry in 39s".
            temporary = "retry in" in lowered or "per minute" in lowered
            exhausted = any(word in lowered for word in ("quota", "billing", "per day", "daily"))
            kind = (LLMErrorKind.QUOTA_EXHAUSTED if exhausted and not temporary
                    else LLMErrorKind.RATE_LIMITED)
            return self._error(kind, "HTTP 429")
        if status >= 500:
            return self._error(LLMErrorKind.UNAVAILABLE, f"HTTP {status}")
        if status == 400 and "model" in lowered and (
            "not found" in lowered or "does not exist" in lowered or "decommission" in lowered
        ):
            return self._error(LLMErrorKind.MODEL_NOT_FOUND, "HTTP 400")
        return self._error(LLMErrorKind.BAD_RESPONSE, f"HTTP {status}")

    def _parse(self, text: str) -> LLMResponse:
        try:
            message = json.loads(text)["choices"][0]["message"]
            calls = []
            for index, raw in enumerate(message.get("tool_calls") or []):
                function = raw["function"]
                arguments = function.get("arguments") or "{}"
                parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
                if not isinstance(parsed, dict):
                    raise ValueError("tool arguments are not an object")
                extra = {k: v for k, v in raw.items() if k not in ("id", "type", "function")}
                calls.append(ToolCall(id=raw.get("id") or f"call_{index}",
                                      name=function["name"], arguments=parsed, extra=extra))
            content = message.get("content")
            if content is not None and not isinstance(content, str):
                raise ValueError("content is not text")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise self._error(LLMErrorKind.BAD_RESPONSE, type(error).__name__) from error
        return LLMResponse(content=content, tool_calls=tuple(calls), provider=self.provider,
                           model=self.model)


def build_client(settings: LLMSettings) -> LLMClient | None:
    """Client for the configured provider, or None for the offline no-LLM mode."""
    if settings.provider == "none":
        return None
    return OpenAICompatibleClient(settings)
