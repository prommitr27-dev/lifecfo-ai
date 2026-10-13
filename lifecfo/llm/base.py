"""Types shared by every LLM provider.

Business logic depends only on `LLMClient`. Adding a provider, free or paid,
means adding a client that satisfies this protocol; nothing else changes.
"""

from enum import StrEnum
from typing import Any, Protocol

from lifecfo.domain.models import Frozen


class ToolSpec(Frozen):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


class ToolCall(Frozen):
    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage(Frozen):
    role: str  # system | user | assistant | tool
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


class LLMResponse(Frozen):
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    provider: str
    model: str


class LLMErrorKind(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTH = "AUTH"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    BAD_RESPONSE = "BAD_RESPONSE"


_USER_MESSAGES = {
    LLMErrorKind.NOT_CONFIGURED: "the AI provider is not fully configured",
    LLMErrorKind.AUTH: "the AI provider rejected the API key",
    LLMErrorKind.RATE_LIMITED: "the free rate limit of the AI provider was reached",
    LLMErrorKind.QUOTA_EXHAUSTED: "the free quota of the AI provider is used up",
    LLMErrorKind.MODEL_NOT_FOUND: "the configured AI model is not available",
    LLMErrorKind.UNAVAILABLE: "the AI provider could not be reached",
    LLMErrorKind.BAD_RESPONSE: "the AI provider returned an unusable answer",
}


class LLMError(Exception):
    def __init__(self, kind: LLMErrorKind, provider: str, detail: str = "") -> None:
        super().__init__(f"{provider}: {kind.value} {detail}".strip())
        self.kind = kind
        self.provider = provider
        self.detail = detail

    @property
    def user_message(self) -> str:
        """Safe to show in the UI: never contains keys or raw provider output."""
        return _USER_MESSAGES[self.kind]


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        """One chat turn. Raises LLMError; never falls back to another provider."""
        ...
