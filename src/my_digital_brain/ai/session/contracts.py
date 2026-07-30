"""Contracts for one logical LLM interaction and its provider turns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import ToolResult, ToolSpec
from ..schemas import (
    AIRequestContext,
    ChatMessage,
    ProviderCallMetadata,
    ProviderUsage,
)
from ..tools import ToolBox

ToolMapping = dict[str, Callable[..., Any]]
DEFAULT_MAX_TOOL_CALLS = 50


class LLMCompletionRequest(BaseModel):
    """One provider request. The provider never executes tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[ChatMessage]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[ToolSpec] = Field(default_factory=list)
    response_format: dict[str, Any] | None = None
    context: AIRequestContext = Field(default_factory=AIRequestContext)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMCompletionResult(BaseModel):
    """Normalized response from exactly one provider request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    assistant_message: ChatMessage
    usage: ProviderUsage | None = None
    metadata: ProviderCallMetadata
    raw_response: dict[str, Any] | None = None


class PendingToolCall(BaseModel):
    """A tool call whose backend interaction requires an external response."""

    call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionEvent(BaseModel):
    """Traceable result for one executed or pending tool call."""

    call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: ToolResult


class LLMSessionContinuation(BaseModel):
    """Data required to resume a paused logical session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    messages: list[ChatMessage]
    pending_tool_calls: list[PendingToolCall] = Field(min_length=1)
    pending_interaction: dict[str, Any] = Field(default_factory=dict)
    tool_events: list[ToolExecutionEvent] = Field(default_factory=list)
    tool_calls_used: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMSessionRequest(BaseModel):
    """Complete configuration for one logical text or structured LLM session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_prompt: str
    messages: list[ChatMessage] = Field(default_factory=list)
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    output_schema: type[BaseModel] | None = None
    toolbox: ToolBox | None = None
    tools_mapping: ToolMapping = Field(default_factory=dict)
    max_tool_calls: int | None = None
    session_id: str = ""
    context: AIRequestContext = Field(default_factory=AIRequestContext)
    metadata: dict[str, Any] = Field(default_factory=dict)
    continuation: LLMSessionContinuation | None = None


class LLMSessionCompleted(BaseModel):
    kind: Literal["completed"] = "completed"
    session_id: str
    messages: list[ChatMessage]
    content: str = ""
    parsed: BaseModel | None = None
    tool_events: list[ToolExecutionEvent] = Field(default_factory=list)
    usage: ProviderUsage | None = None
    metadata: ProviderCallMetadata | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class LLMSessionAwaitingTool(BaseModel):
    kind: Literal["awaiting_tool"] = "awaiting_tool"
    session_id: str
    messages: list[ChatMessage]
    continuation: LLMSessionContinuation
    tool_events: list[ToolExecutionEvent] = Field(default_factory=list)
    usage: ProviderUsage | None = None
    metadata: ProviderCallMetadata | None = None


class LLMSessionFailed(BaseModel):
    kind: Literal["failed"] = "failed"
    session_id: str
    messages: list[ChatMessage]
    error: str
    tool_events: list[ToolExecutionEvent] = Field(default_factory=list)
    metadata: ProviderCallMetadata | None = None


LLMSessionResult = LLMSessionCompleted | LLMSessionAwaitingTool | LLMSessionFailed
