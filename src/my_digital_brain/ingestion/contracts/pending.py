from __future__ import annotations

from typing import Any

from pydantic import Field

from my_digital_brain.ai.schemas import ChatMessage
from my_digital_brain.ai.session import LLMSessionContinuation
from my_digital_brain.ingestion.contracts.base import IngestionModel


class IngestionPendingInteraction(IngestionModel):
    """Channel-neutral external interaction produced during ingestion."""

    stage: str
    session_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    clarification_packet: dict[str, Any] | None = None
    continuation: LLMSessionContinuation | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
