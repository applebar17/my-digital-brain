from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.ai.schemas import ChatMessage


class AgenticToolEvent(AgenticModel):
    tool_name: str
    status: str
    output: str | None = None
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AgenticStateRunResult(AgenticModel):
    state_id: AgenticStateId
    assistant_text: str | None = None
    message_delta: list[ChatMessage] = Field(default_factory=list)
    structured_output: dict[str, Any] | None = None
    tool_events: list[AgenticToolEvent] = Field(default_factory=list)
    handoff_target: str | None = None
    handoff_arguments: dict[str, Any] = Field(default_factory=dict)
    terminal: bool = True
    status: str = "ok"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgenticRunResult(AgenticModel):
    final_text: str | None = None
    visited_states: list[AgenticStateId] = Field(default_factory=list)
    state_results: list[AgenticStateRunResult] = Field(default_factory=list)
    status: str = "ok"
    pending_process_hints: list[dict[str, Any]] = Field(default_factory=list)
    compact_trace: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgenticStateInvocation(AgenticModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    state_id: AgenticStateId
    context_payload: Any
    execution_context: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
