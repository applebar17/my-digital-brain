from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.enums import NeutralMessageKind, ToolResultStatus
from my_digital_brain.core.ids import new_uuid


class ToolCall(AgenticModel):
    tool_call_id: str = Field(default_factory=new_uuid)
    name: str = Field(description="Model-visible tool name.")
    arguments: dict[str, Any] = Field(default_factory=dict)
    target_state: str | None = Field(
        default=None,
        description="Optional target state or process receiving this tool call.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolOutput(AgenticModel):
    tool_call_id: str
    name: str
    status: ToolResultStatus = ToolResultStatus.OK
    content: str | None = Field(
        default=None,
        description="Compact model-facing tool output summary.",
    )
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NeutralConversationMessage(AgenticModel):
    message_id: str = Field(default_factory=new_uuid)
    kind: NeutralMessageKind
    content: str | None = None
    tool_call: ToolCall | None = None
    tool_output: ToolOutput | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shape(self) -> NeutralConversationMessage:
        if self.kind == NeutralMessageKind.ASSISTANT_TOOL_CALL and self.tool_call is None:
            raise ValueError("assistant_tool_call messages require tool_call.")
        if self.kind != NeutralMessageKind.ASSISTANT_TOOL_CALL and self.tool_call is not None:
            raise ValueError("tool_call is only valid for assistant_tool_call messages.")
        if self.kind == NeutralMessageKind.TOOL_OUTPUT and self.tool_output is None:
            raise ValueError("tool_output messages require tool_output.")
        if self.kind != NeutralMessageKind.TOOL_OUTPUT and self.tool_output is not None:
            raise ValueError("tool_output is only valid for tool_output messages.")
        if self.kind in {
            NeutralMessageKind.USER,
            NeutralMessageKind.ASSISTANT,
            NeutralMessageKind.COMPACTED_SUMMARY,
        } and not self.content:
            raise ValueError(f"{self.kind} messages require content.")
        return self

    @classmethod
    def user(cls, content: str, **metadata: Any) -> NeutralConversationMessage:
        return cls(kind=NeutralMessageKind.USER, content=content, metadata=metadata)

    @classmethod
    def assistant(cls, content: str, **metadata: Any) -> NeutralConversationMessage:
        return cls(kind=NeutralMessageKind.ASSISTANT, content=content, metadata=metadata)

    @classmethod
    def assistant_tool_call(
        cls,
        name: str,
        arguments: dict[str, Any] | None = None,
        **metadata: Any,
    ) -> NeutralConversationMessage:
        return cls(
            kind=NeutralMessageKind.ASSISTANT_TOOL_CALL,
            tool_call=ToolCall(name=name, arguments=arguments or {}),
            metadata=metadata,
        )

    @classmethod
    def tool_output_message(
        cls,
        *,
        tool_call_id: str,
        name: str,
        status: ToolResultStatus = ToolResultStatus.OK,
        content: str | None = None,
        data: dict[str, Any] | None = None,
        **metadata: Any,
    ) -> NeutralConversationMessage:
        return cls(
            kind=NeutralMessageKind.TOOL_OUTPUT,
            tool_output=ToolOutput(
                tool_call_id=tool_call_id,
                name=name,
                status=status,
                content=content,
                data=data or {},
            ),
            metadata=metadata,
        )

    @classmethod
    def compacted_summary(cls, content: str, **metadata: Any) -> NeutralConversationMessage:
        return cls(
            kind=NeutralMessageKind.COMPACTED_SUMMARY,
            content=content,
            metadata=metadata,
        )
