from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.drafts import (
    ClarificationRequestDraft,
    EvidenceSpanDraft,
)
from my_digital_brain.ingestion.contracts.shared import TemporalScope
from my_digital_brain.ingestion.contracts.source import EvidenceRef


class MemoryLogKind(StrEnum):
    OBSERVATION = "observation"
    UPDATE = "update"
    CORRECTION = "correction"
    STATUS_CHANGE = "status_change"
    PREFERENCE = "preference"
    RELATIONSHIP_NOTE = "relationship_note"
    EVENT_DETAIL = "event_detail"
    MEDIA_NOTE = "media_note"
    OTHER = "other"


class MemoryLogImportance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemoryLogSourceKind(StrEnum):
    USER_STATED = "user_stated"
    LLM_INFERRED = "llm_inferred"
    SYSTEM_DERIVED = "system_derived"


class MemoryLogLinkDraft(IngestionModel):
    target_ref: str = Field(
        description="Candidate ref or graph alias for a domain/context node linked to the log.",
    )
    role: str | None = Field(
        default=None,
        description="Short role for this target, such as person, place, topic, or context.",
    )
    primary: bool = Field(
        default=False,
        description="Whether this host is the primary UI anchor for the log.",
    )
    note: str | None = Field(
        default=None,
        description="Optional short reason why this target is linked to the log.",
    )


class MediaAssetRefDraft(IngestionModel):
    media_ref: str = Field(
        description=(
            "Caller-provided media handle or local ref. This is a placeholder; "
            "backend persistence resolves it into MediaAsset records later."
        ),
    )
    role: str | None = Field(
        default=None,
        description="Media role such as evidence, attachment, or memory_photo.",
    )
    caption_hint: str | None = Field(
        default=None,
        description="Short caption or description supported by the source.",
    )
    note: str | None = Field(
        default=None,
        description="Optional note explaining how the media supports this log.",
    )


class MemoryLogDraft(IngestionModel):
    """LLM-facing lightweight memory atom draft."""

    local_ref: str = Field(
        description="Scoped local reference such as MEMORY_LOG_001.",
    )
    log_text: str = Field(
        description=(
            "Short human-readable memory brick. It must preserve the specific "
            "dated update or observation without becoming a full domain node."
        ),
    )
    log_kind: MemoryLogKind = Field(
        default=MemoryLogKind.OBSERVATION,
        description="Lightweight kind for routing, filtering, and future summary refresh.",
    )
    host_refs: list[MemoryLogLinkDraft] = Field(
        default_factory=list,
        description=(
            "Domain or context nodes whose timeline should show this log. "
            "Use candidate refs or graph aliases, not raw database IDs."
        ),
    )
    involved_refs: list[MemoryLogLinkDraft] = Field(
        default_factory=list,
        description="Additional domain/context nodes involved in the memory.",
    )
    relationship_context_refs: list[str] = Field(
        default_factory=list,
        description="Relationship context refs updated or explained by this log.",
    )
    media_refs: list[MediaAssetRefDraft] = Field(
        default_factory=list,
        description="Media placeholders to resolve into MediaAsset records later.",
    )
    happened_at: str | None = Field(
        default=None,
        description="User-stated or normalized point in time when the memory happened.",
    )
    temporal_scope: TemporalScope | None = Field(
        default=None,
        description="Fuzzy or bounded temporal information for this memory.",
    )
    source_kind: MemoryLogSourceKind = Field(
        default=MemoryLogSourceKind.USER_STATED,
        description="Whether the memory is user-stated, inferred, or system-derived.",
    )
    original_user_words: str | None = Field(
        default=None,
        description="Source wording worth preserving because it carries memory tone.",
    )
    importance: MemoryLogImportance = Field(
        default=MemoryLogImportance.LOW,
        description="Lightweight importance hint; summary refresh remains a later wave.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional confidence only when the process can justify it.",
    )
    evidence: list[EvidenceSpanDraft] = Field(
        default_factory=list,
        description="Short source spans supporting the log draft.",
    )
    ambiguity_flags: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False

    @model_validator(mode="after")
    def _validate_hosts(self) -> "MemoryLogDraft":
        if not self.log_text.strip():
            raise ValueError("MemoryLogDraft requires non-empty log_text.")
        if not self.host_refs:
            raise ValueError("MemoryLogDraft requires at least one host_ref.")
        primary_count = sum(1 for host in self.host_refs if host.primary)
        if len(self.host_refs) > 1 and primary_count != 1:
            raise ValueError(
                "MemoryLogDraft with multiple host_refs requires exactly one primary host."
            )
        return self


class MemoryLogDraftBatch(IngestionModel):
    candidates: list[MemoryLogDraft] = Field(default_factory=list)


class MemoryLogLink(IngestionModel):
    target_id: str = Field(description="Resolved graph node id or backend graph ref.")
    target_label: str | None = Field(
        default=None,
        description="Graph label for the resolved target when known.",
    )
    relationship_type: Literal[
        "HAS_MEMORY_LOG",
        "INVOLVES",
        "UPDATES_RELATIONSHIP",
        "HAS_MEDIA",
    ] = Field(description="Graph relationship intended for this link.")
    role: str | None = Field(default=None)
    primary: bool = Field(
        default=False,
        description="Primary host marker for HAS_MEMORY_LOG links.",
    )


class MediaAsset(IngestionModel):
    media_asset_id: str = Field(default_factory=new_uuid)
    media_type: Literal["image", "audio", "video", "document", "other"] = Field(
        default="other",
        description="Broad media category.",
    )
    mime_type: str | None = Field(default=None)
    storage_uri: str | None = Field(
        default=None,
        description="Durable URI when media storage has resolved the asset.",
    )
    storage_key: str | None = Field(
        default=None,
        description="Backend storage key when URI exposure is not desired.",
    )
    checksum: str | None = Field(
        default=None,
        description="Checksum used for dedupe and integrity when available.",
    )
    caption: str | None = Field(default=None)
    captured_at: str | None = Field(default=None)
    source_refs: list[str] = Field(default_factory=list)
    lifecycle_state: str = Field(default="active")
    metadata: dict[str, object] = Field(default_factory=dict)


class MemoryLog(IngestionModel):
    """Backend-enriched memory atom ready for validation or persistence."""

    memory_log_id: str = Field(default_factory=new_uuid)
    local_ref: str | None = Field(default=None)
    log_text: str = Field(description="Short human-readable memory brick.")
    log_kind: MemoryLogKind = MemoryLogKind.OBSERVATION
    primary_host_target_id: str | None = Field(
        default=None,
        description="Default UI anchor for this log.",
    )
    primary_host_target_label: str | None = None
    host_target_ids: list[str] = Field(default_factory=list)
    involved_target_ids: list[str] = Field(default_factory=list)
    links: list[MemoryLogLink] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)
    source_kind: MemoryLogSourceKind = MemoryLogSourceKind.USER_STATED
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    extraction_run_ids: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    temporal_scope: TemporalScope | None = None
    happened_at: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: MemoryLogImportance = MemoryLogImportance.LOW
    lifecycle_state: str = Field(default="active")
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_host_links(self) -> "MemoryLog":
        host_links = [
            link for link in self.links if link.relationship_type == "HAS_MEMORY_LOG"
        ]
        host_ids = set(self.host_target_ids)
        host_ids.update(link.target_id for link in host_links)
        if self.primary_host_target_id:
            host_ids.add(self.primary_host_target_id)
        if not host_ids:
            raise ValueError("MemoryLog requires at least one host target.")

        primary_links = [link for link in host_links if link.primary]
        if len(primary_links) > 1:
            raise ValueError("MemoryLog can have at most one primary HAS_MEMORY_LOG link.")
        if len(host_ids) > 1 and len(primary_links) != 1 and not self.primary_host_target_id:
            raise ValueError(
                "MemoryLog with multiple host targets requires one primary host."
            )
        if self.primary_host_target_id and self.primary_host_target_id not in host_ids:
            raise ValueError("primary_host_target_id must be one of the host targets.")
        return self


class NodeFieldPatchDraft(IngestionModel):
    target_ref: str = Field(description="Candidate ref or graph alias receiving the patch.")
    operation: Literal["set", "append", "remove"] = Field(
        description="Requested field patch operation.",
    )
    path: str = Field(description="Flat or dotted target field path.")
    value_text: str | None = Field(default=None)
    previous_value_text: str | None = Field(default=None)
    reason: str = Field(description="Why this patch is safe and useful.")
    evidence: list[EvidenceSpanDraft] = Field(default_factory=list)


class NodeUpdatePlanDraft(IngestionModel):
    reason: str | None = Field(
        default=None,
        description="Concise reason for the proposed node update plan.",
    )
    memory_logs: list[MemoryLogDraft] = Field(
        default_factory=list,
        description="MemoryLog drafts to create as lightweight memory atoms.",
    )
    field_patches: list[NodeFieldPatchDraft] = Field(
        default_factory=list,
        description="Safe explicit field patches. Prefer MemoryLog for ordinary updates.",
    )
    clarification: ClarificationRequestDraft | None = Field(
        default=None,
        description="Blocking clarification required before update execution can continue.",
    )
    context_gaps: list[str] = Field(
        default_factory=list,
        description="Missing context that should be retrieved before update execution.",
    )

    @model_validator(mode="after")
    def _validate_has_next_step(self) -> "NodeUpdatePlanDraft":
        if not (
            self.memory_logs
            or self.field_patches
            or self.clarification
            or self.context_gaps
        ):
            raise ValueError(
                "Node update plan requires memory_logs, field_patches, "
                "clarification, or context gaps."
            )
        return self
