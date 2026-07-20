from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.enums import ClarificationStatus


class IdentityLookupStatus(StrEnum):
    NO_CANDIDATES = "no_candidates"
    ONE_CANDIDATE = "one_candidate"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    FUZZY_CANDIDATES_ONLY = "fuzzy_candidates_only"


class EntityResolutionAction(StrEnum):
    CREATE_NEW = "create_new"
    ATTACH_TO_EXISTING = "attach_to_existing"
    REQUEST_CLARIFICATION = "request_clarification"
    IGNORE_OR_DEFER = "ignore_or_defer"


class ReferenceObjectKind(StrEnum):
    NODE = "node"
    MEMORY = "memory"
    EDGE = "edge"
    CONTEXT = "context"
    MEDIA = "media"
    SOURCE = "source"
    CLAIM = "claim"


class ReferenceStatus(StrEnum):
    EXISTING = "existing"
    PROPOSED = "proposed"


class IdentityMatchKind(StrEnum):
    EXACT_NAME = "exact_name"
    EXACT_ALIAS = "exact_alias"
    NAME_TOKEN = "name_token"
    FUZZY_HINT = "fuzzy_hint"


_CANDIDATE_REF_RE = re.compile(r"^CANDIDATE_[A-Z][A-Z0-9_]*_[0-9]{3,6}$")
_NODE_REF_RE = re.compile(r"^NODE_[0-9]{6}$")
_EXISTING_REF_RE = re.compile(r"^(?:OWNER|NODE_[0-9]{6})$")
_MODEL_REF_RE = re.compile(
    r"^(?:OWNER|CANDIDATE_[A-Z][A-Z0-9_]*_[0-9]{3,6}|"
    r"(?:NODE|REL|MEMORY|CONTEXT|MEDIA|SOURCE|CLAIM)_[0-9]{6})$",
)


class EntityLookupRequest(IngestionModel):
    """Backend-built lookup input derived from a planned candidate."""

    candidate_ref: str
    entity_type: str = Field(min_length=1)
    display_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    typed_identity_values: dict[str, list[str]] = Field(default_factory=dict)
    max_candidates: int = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def _validate_candidate_ref(self) -> "EntityLookupRequest":
        _require_candidate_ref(self.candidate_ref)
        return self


class EntityLookupRelatedContext(IngestionModel):
    relationship_summaries: list[str] = Field(default_factory=list)
    relevant_memory_summaries: list[str] = Field(default_factory=list)
    place_hints: list[str] = Field(default_factory=list)
    temporal_hints: list[str] = Field(default_factory=list)


class EntityLookupCandidate(IngestionModel):
    """Safe model-facing projection of an existing graph candidate."""

    ref: str
    label: str = Field(min_length=1)
    display_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    match_kind: IdentityMatchKind
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    related_context: EntityLookupRelatedContext = Field(
        default_factory=EntityLookupRelatedContext,
    )

    @model_validator(mode="after")
    def _validate_existing_node_ref(self) -> "EntityLookupCandidate":
        if not _NODE_REF_RE.fullmatch(self.ref):
            raise ValueError("Lookup candidates must use existing NODE references.")
        return self


class EntityLookupResult(IngestionModel):
    candidate_ref: str
    status: IdentityLookupStatus
    candidates: list[EntityLookupCandidate] = Field(default_factory=list)
    guidance: str | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> "EntityLookupResult":
        _require_candidate_ref(self.candidate_ref)
        if self.status == IdentityLookupStatus.NO_CANDIDATES and self.candidates:
            raise ValueError("No-candidate lookup results cannot contain candidates.")
        if self.status == IdentityLookupStatus.ONE_CANDIDATE and len(self.candidates) != 1:
            raise ValueError("One-candidate lookup results require exactly one candidate.")
        if self.status == IdentityLookupStatus.MULTIPLE_CANDIDATES and len(self.candidates) < 2:
            raise ValueError("Multiple-candidate results require at least two candidates.")
        return self


class EntityLookupContextPacket(IngestionModel):
    """Bounded candidate context rendered for a planning or extraction call."""

    candidate_ref: str
    entity_type: str = Field(min_length=1)
    proposed_display_name: str | None = None
    proposed_aliases: list[str] = Field(default_factory=list)
    lookup: EntityLookupResult
    guidance: str | None = None

    @model_validator(mode="after")
    def _validate_packet_refs(self) -> "EntityLookupContextPacket":
        _require_candidate_ref(self.candidate_ref)
        if self.lookup.candidate_ref != self.candidate_ref:
            raise ValueError("Lookup result must target the packet candidate.")
        return self


class EntityResolutionProposal(IngestionModel):
    """LLM decision proposal validated before backend write planning."""

    candidate_ref: str
    action: EntityResolutionAction
    target_ref: str | None = None
    reason: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_action_target(self) -> "EntityResolutionProposal":
        _require_candidate_ref(self.candidate_ref)
        if self.action == EntityResolutionAction.ATTACH_TO_EXISTING:
            if self.target_ref is None:
                raise ValueError("Existing-node attachment requires target_ref.")
            if not _EXISTING_REF_RE.fullmatch(self.target_ref):
                raise ValueError("Existing-node attachment requires OWNER or NODE ref.")
        elif self.target_ref is not None:
            raise ValueError("target_ref is allowed only for existing-node attachment.")
        return self


class SessionClarificationContext(IngestionModel):
    """Transient resolution state carried through normal session history."""

    session_id: str = Field(min_length=1)
    candidate_ref: str
    lookup_packet: EntityLookupContextPacket
    question: str = Field(min_length=1)
    history_message_refs: list[str] = Field(default_factory=list)
    question_message_ref: str | None = None
    answer_message_ref: str | None = None
    status: ClarificationStatus = ClarificationStatus.WAITING_FOR_USER
    owner_ref: Literal["OWNER"] = OWNER_ALIAS

    @model_validator(mode="after")
    def _validate_candidate_ref(self) -> "SessionClarificationContext":
        _require_candidate_ref(self.candidate_ref)
        if self.lookup_packet.candidate_ref != self.candidate_ref:
            raise ValueError("Clarification packet must target the candidate ref.")
        return self


class ReferenceRegistryEntry(IngestionModel):
    """Backend registry entry; backend_id is never model-facing."""

    ref: str
    object_kind: ReferenceObjectKind
    status: ReferenceStatus
    label: str = Field(min_length=1)
    backend_id: str | None = None
    graph_scope: str = Field(min_length=1)
    session_scope: str = Field(min_length=1)
    display_label: str | None = None
    aliases: list[str] = Field(default_factory=list)
    is_owner: bool = False

    @model_validator(mode="after")
    def _validate_registry_entry(self) -> "ReferenceRegistryEntry":
        if not _MODEL_REF_RE.fullmatch(self.ref):
            raise ValueError("Malformed model-facing reference.")
        if self.status == ReferenceStatus.EXISTING and not self.backend_id:
            raise ValueError("Existing references require a backend ID.")
        if self.status == ReferenceStatus.PROPOSED and self.backend_id is not None:
            raise ValueError("Proposed references cannot contain a backend ID.")
        if self.ref == OWNER_ALIAS:
            if not self.is_owner or self.object_kind != ReferenceObjectKind.NODE:
                raise ValueError("OWNER must be an owner node registry entry.")
            if self.label != "Person":
                raise ValueError("OWNER must use the Person label.")
        elif self.is_owner:
            raise ValueError("Only OWNER may be marked as the owner reference.")
        return self

    def model_facing_payload(self) -> dict[str, Any]:
        """Return the safe projection used in model-facing context packets."""

        payload = {
            "ref": self.ref,
            "object_kind": ReferenceObjectKind(self.object_kind).value,
            "status": ReferenceStatus(self.status).value,
            "label": self.label,
            "display_label": self.display_label,
            "aliases": list(self.aliases),
        }
        return {
            key: value
            for key, value in payload.items()
            if value not in (None, "", [], {})
        }


def _require_candidate_ref(value: str) -> None:
    if not _CANDIDATE_REF_RE.fullmatch(value):
        raise ValueError("Candidate refs must use the CANDIDATE_*_NNN format.")
