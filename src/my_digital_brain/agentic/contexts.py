from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.enums import (
    ChannelModality,
    ResponseRenderStyle,
    ToolResultStatus,
)
from my_digital_brain.agentic.messages import NeutralConversationMessage
from my_digital_brain.core.ids import new_uuid


class ChannelSessionMetadata(AgenticModel):
    """Backend-owned channel/session metadata.

    This object may be passed between backend states, but it must not be passed
    directly into model-facing prompts.
    """

    channel: str
    conversation_id: str
    owner_id: str
    session_id: str | None = None
    sender_id: str | None = None
    message_id: str | None = None
    received_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelContextProjection(AgenticModel):
    """Minimal model-facing projection of channel metadata when it is useful."""

    modality: ChannelModality = ChannelModality.TEXT
    render_style: ResponseRenderStyle = ResponseRenderStyle.PLAIN_TEXT
    source_refs: list[str] = Field(default_factory=list)
    transcript_uncertainty: str | None = None
    current_time: datetime | None = None
    timezone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingProcessContext(AgenticModel):
    process_id: str
    kind: str
    status: str
    question: str | None = None
    unresolved_targets: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    compact_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationContext(AgenticModel):
    context_id: str = Field(default_factory=new_uuid)
    current_message: NeutralConversationMessage
    history: list[NeutralConversationMessage] = Field(default_factory=list)
    compacted_summary: str | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    pending_process: PendingProcessContext | None = None
    channel_metadata: ChannelSessionMetadata | None = None
    channel_projection: ChannelContextProjection | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_facing_payload(self) -> dict[str, Any]:
        """Return prompt-safe context without backend-only channel metadata."""

        return self.model_dump(
            mode="json",
            exclude={"channel_metadata"},
            exclude_none=True,
        )


class EvidenceSpan(AgenticModel):
    evidence_id: str = Field(default_factory=new_uuid)
    text: str
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    source_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceContext(AgenticModel):
    source_id: str
    normalized_text: str | None = None
    transcript_text: str | None = None
    media_refs: list[str] = Field(default_factory=list)
    source_time: datetime | None = None
    received_at: datetime | None = None
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MentionContextItem(AgenticModel):
    mention_id: str = Field(default_factory=new_uuid)
    kind: str
    text: str
    evidence_text: str | None = None
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    hints: dict[str, Any] = Field(default_factory=dict)


class MentionScanContext(AgenticModel):
    mention_scan_id: str = Field(default_factory=new_uuid)
    source_id: str
    mentions: list[MentionContextItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphContextPackage(AgenticModel):
    package_id: str = Field(default_factory=new_uuid)
    aliases: dict[str, str] = Field(default_factory=dict)
    candidate_matches: list[dict[str, Any]] = Field(default_factory=list)
    relationship_contexts: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summaries: list[dict[str, Any]] = Field(default_factory=list)
    known_ambiguities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningContext(AgenticModel):
    source: SourceContext
    conversation: ConversationContext
    mention_scan: MentionScanContext | None = None
    graph_context: GraphContextPackage | None = None
    pending_clarification_answer: str | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    prior_tool_outputs: list["ToolResultContext"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionTaskContext(AgenticModel):
    task_id: str
    task_type: str
    schema_id: str
    evidence: EvidenceSpan
    graph_aliases: dict[str, str] = Field(default_factory=dict)
    local_candidate_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateGraphContext(AgenticModel):
    candidate_graph_id: str = Field(default_factory=new_uuid)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    local_refs: dict[str, str] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolutionContext(AgenticModel):
    candidate_graph: CandidateGraphContext
    graph_context: GraphContextPackage | None = None
    registries: dict[str, list[str]] = Field(default_factory=dict)
    resolver_constraints: dict[str, Any] = Field(default_factory=dict)
    pending_answer_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResultContext(AgenticModel):
    result_id: str = Field(default_factory=new_uuid)
    tool_name: str
    status: ToolResultStatus = ToolResultStatus.OK
    summary: str
    important_refs: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_action: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnswerContext(AgenticModel):
    question: str
    context_package: dict[str, Any]
    evidence_rules: list[str] = Field(default_factory=list)
    answer_style_hints: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
