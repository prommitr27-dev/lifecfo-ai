"""Provider-agnostic LLM access. No provider is required: the default is none."""

from lifecfo.llm.base import (
    ChatMessage,
    LLMClient,
    LLMError,
    LLMErrorKind,
    LLMResponse,
    ToolCall,
    ToolSpec,
)
from lifecfo.llm.config import PROVIDERS, LLMSettings, load_env_file
from lifecfo.llm.openai_compatible import OpenAICompatibleClient, build_client

__all__ = [
    "PROVIDERS",
    "ChatMessage",
    "LLMClient",
    "LLMError",
    "LLMErrorKind",
    "LLMResponse",
    "LLMSettings",
    "OpenAICompatibleClient",
    "ToolCall",
    "ToolSpec",
    "build_client",
    "load_env_file",
]
