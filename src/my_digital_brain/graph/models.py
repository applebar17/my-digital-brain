from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from my_digital_brain.core.models import GraphRecordBase, GraphRelationshipBase
from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.registry import (
    CORE_NODE_LABELS,
    GRAPH_MUTABLE_RELATIONSHIP_TYPES,
    validate_node_label,
)


class GraphNodeModel(GraphRecordBase):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=True)

    label: ClassVar[str]


class PersonNode(GraphNodeModel):
    label: ClassVar[str] = "Person"

    is_owner: bool = False
    display_name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    known_since: str | None = None
    status: str | None = None


class EventNode(GraphNodeModel):
    label: ClassVar[str] = "Event"

    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None


class PlaceNode(GraphNodeModel):
    label: ClassVar[str] = "Place"

    name: str | None = None
    normalized_name: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_precision: str | None = None


class OrganizationNode(GraphNodeModel):
    label: ClassVar[str] = "Organization"

    name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    domain: str | None = None


class ObjectNode(GraphNodeModel):
    label: ClassVar[str] = "Object"

    name: str | None = None
    normalized_name: str | None = None
    category: str | None = None
    owner_hint: str | None = None


class AnimalNode(GraphNodeModel):
    label: ClassVar[str] = "Animal"

    name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    status: str | None = None
    known_since: str | None = None
    date_of_birth: str | None = None
    date_of_death: str | None = None
    owner_hint: str | None = None


class SocialCircleNode(GraphNodeModel):
    label: ClassVar[str] = "SocialCircle"

    name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    circle_type: str | None = None
    source_kind: str | None = None


class GraphNodeCreateModel(BaseModel):
    """Explicit, model-facing writable fields for one graph-node creation tool."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        description=(
            "Short source-grounded description to store on the node. Do not use a "
            "planning-only field such as summary."
        ),
    )


class PersonNodeCreate(GraphNodeCreateModel):
    display_name: str = Field(description="Person's human-readable name from the source.")
    aliases: list[str] = Field(
        default_factory=list,
        description="Explicit alternate names or nicknames from the source.",
    )
    known_since: str | None = Field(default=None, description="Source-supported known-since hint.")
    status: str | None = Field(default=None, description="Source-supported relationship status.")


class EventNodeCreate(GraphNodeCreateModel):
    title: str = Field(description="Short human-readable event title.")
    aliases: list[str] = Field(
        default_factory=list,
        description="Explicit alternate event names or spelling variants from the source.",
    )
    started_at: str | None = Field(default=None, description="Known event start time.")
    ended_at: str | None = Field(default=None, description="Known event end time.")


class PlaceNodeCreate(GraphNodeCreateModel):
    name: str = Field(description="Human-readable place name from the source.")
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_precision: str | None = None


class OrganizationNodeCreate(GraphNodeCreateModel):
    name: str = Field(description="Human-readable organization name from the source.")
    aliases: list[str] = Field(default_factory=list)
    domain: str | None = None


class ObjectNodeCreate(GraphNodeCreateModel):
    name: str = Field(description="Human-readable object name from the source.")
    category: str | None = None
    owner_hint: str | None = None


class AnimalNodeCreate(GraphNodeCreateModel):
    name: str = Field(description="Human-readable animal name from the source.")
    aliases: list[str] = Field(default_factory=list)
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    status: str | None = None
    known_since: str | None = None
    date_of_birth: str | None = None
    date_of_death: str | None = None
    owner_hint: str | None = None


class SocialCircleNodeCreate(GraphNodeCreateModel):
    name: str = Field(description="Human-readable social-circle name from the source.")
    aliases: list[str] = Field(default_factory=list)
    circle_type: str | None = None
    source_kind: str | None = None


class TopicNodeCreate(GraphNodeCreateModel):
    name: str = Field(description="Human-readable topic name from the source.")
    aliases: list[str] = Field(default_factory=list)


class PerceptionNodeCreate(GraphNodeCreateModel):
    perception_type: str = Field(
        description="Source-grounded kind of perception, such as mood, impression, or feeling."
    )
    source_kind: str | None = Field(
        default=None,
        description="Source-grounded origin of the perception, such as user_statement.",
    )


class RelationshipContextNodeCreate(GraphNodeCreateModel):
    relationship_type: str = Field(
        description="Source-grounded broad relationship type, such as friendship, family, or romantic."
    )
    relationship_kind: str | None = Field(
        default=None,
        description="Optional finer relationship kind, such as colleague or sibling.",
    )
    relationship_detail: str | None = Field(
        default=None,
        description="Specific source wording that describes the relationship.",
    )
    status: str | None = Field(
        default=None, description="Source-grounded current relationship status."
    )
    closeness: str | None = Field(
        default=None, description="Source-grounded closeness description."
    )


class GraphNodePatchModel(BaseModel):
    """Explicit model-facing fields that may be changed on an existing node."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        description="Replacement source-grounded description, or null to leave unchanged.",
    )


class PersonNodePatch(GraphNodePatchModel):
    display_name: str | None = None
    aliases: list[str] | None = None
    known_since: str | None = None
    status: str | None = None


class EventNodePatch(GraphNodePatchModel):
    title: str | None = None
    aliases: list[str] | None = None
    started_at: str | None = None
    ended_at: str | None = None


class PlaceNodePatch(GraphNodePatchModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_precision: str | None = None


class OrganizationNodePatch(GraphNodePatchModel):
    name: str | None = None
    aliases: list[str] | None = None
    domain: str | None = None


class ObjectNodePatch(GraphNodePatchModel):
    name: str | None = None
    category: str | None = None
    owner_hint: str | None = None


class AnimalNodePatch(GraphNodePatchModel):
    name: str | None = None
    aliases: list[str] | None = None
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    status: str | None = None
    known_since: str | None = None
    date_of_birth: str | None = None
    date_of_death: str | None = None
    owner_hint: str | None = None


class SocialCircleNodePatch(GraphNodePatchModel):
    name: str | None = None
    aliases: list[str] | None = None
    circle_type: str | None = None
    source_kind: str | None = None


class TopicNodePatch(GraphNodePatchModel):
    name: str | None = None
    aliases: list[str] | None = None


class PerceptionContextCreate(BaseModel):
    """Explicit request to create and attach one Perception."""

    model_config = ConfigDict(extra="forbid")

    target_ref: str = Field(
        description="Existing, bound model ref for the graph object this perception concerns."
    )
    perception: PerceptionNodeCreate = Field(
        description="Explicit writable fields for the new Perception node."
    )


class RelationshipContextCreate(BaseModel):
    """Explicit request to create and attach one RelationshipContext."""

    model_config = ConfigDict(extra="forbid")

    participant_refs: list[str] = Field(
        min_length=2,
        description=(
            "At least two existing, bound model refs for the participants in this relationship."
        ),
    )
    relationship_context: RelationshipContextNodeCreate = Field(
        description="Explicit writable fields for the new RelationshipContext node."
    )

    @model_validator(mode="after")
    def _validate_distinct_participants(self) -> "RelationshipContextCreate":
        if len(set(self.participant_refs)) != len(self.participant_refs):
            raise ValueError("participant_refs must contain each participant ref only once.")
        return self


class MemoryLogCreate(BaseModel):
    """Explicit model-facing input for creating a linked MemoryLog."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Short user-facing timeline headline for one memory atom.")
    log_text: str = Field(
        description="Compact self-contained detail for the same memory atom; never the full source story."
    )
    host_target_ids: list[str] = Field(description="Model refs of host nodes for this log.")
    primary_host_target_id: str | None = Field(
        default=None,
        description="Main host ref when this log has more than one host.",
    )
    involved_target_ids: list[str] = Field(default_factory=list)
    relationship_context_target_ids: list[str] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)
    log_kind: str | None = None
    source_kind: str | None = None
    happened_at: str | None = None


class GraphRelationshipWrite(BaseModel):
    """Explicit writable fields for one non-destructive graph relationship."""

    model_config = ConfigDict(extra="forbid")

    relationship_type: str = Field(
        description="Supported relationship type from the graph relationship enum.",
        json_schema_extra={"enum": list(GRAPH_MUTABLE_RELATIONSHIP_TYPES)},
    )
    from_id: str = Field(description="Source model ref from the active context.")
    to_id: str = Field(description="Target model ref from the active context.")
    description: str | None = None
    relationship_kind: str | None = Field(
        default=None,
        description="Human relationship detail such as colleague or sibling; do not invent a relationship type.",
    )
    relationship_detail: str | None = Field(
        default=None,
        description="Specific source wording for the relationship, such as brother or university friend.",
    )
    role: str | None = None
    primary: bool | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    original_time_text: str | None = None
    emotional_summary: str | None = None
    emotional_valence: str | None = None
    emotional_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    emotion_tags: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RelationshipStateWrite(BaseModel):
    """Explicit writable state for one RelationshipContext."""

    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(description="RelationshipContext model ref from the active context.")
    status: str | None = None
    closeness: str | None = None
    source_kind: str | None = None
    make_current: bool = Field(
        default=True,
        description="Whether this state becomes the context's current state.",
    )


class TopicNode(GraphNodeModel):
    label: ClassVar[str] = "Topic"

    name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)


class SourceNode(GraphNodeModel):
    label: ClassVar[str] = "Source"

    source_type: str | None = None
    channel: str | None = None
    external_id: str | None = None
    source_created_at: str | None = None
    received_at: str | None = None
    content_ref: str | None = None
    transcript_ref: str | None = None
    derived_from_source_id: str | None = None
    checksum: str | None = None


class ClaimNode(GraphNodeModel):
    label: ClassVar[str] = "Claim"

    text: str | None = None
    claim_type: str | None = None


class PerceptionNode(GraphNodeModel):
    label: ClassVar[str] = "Perception"

    perception_type: str | None = None
    target_type: str | None = None
    source_kind: str | None = None


class RelationshipContextNode(GraphNodeModel):
    label: ClassVar[str] = "RelationshipContext"

    relationship_type: str | None = None
    relationship_kind: str | None = None
    relationship_detail: str | None = None
    status: str | None = None
    closeness: str | None = None


class ProfileMemoryNode(GraphNodeModel):
    label: ClassVar[str] = "ProfileMemory"

    profile_key: str | None = None
    category: str | None = None
    value: str | None = None
    stability: str | None = None
    visibility: str | None = None


class ContactPointNode(GraphNodeModel):
    label: ClassVar[str] = "ContactPoint"

    kind: str | None = None
    value: str | None = None
    normalized_value: str | None = None
    label_text: str | None = Field(default=None, alias="label")
    is_primary: bool | None = None


class ExternalReferenceNode(GraphNodeModel):
    label: ClassVar[str] = "ExternalReference"

    provider: str | None = None
    external_id: str | None = None
    url: str | None = None
    label_text: str | None = Field(default=None, alias="label")
    retrieved_at: str | None = None
    expires_at: str | None = None


class ExtractionRunNode(GraphNodeModel):
    label: ClassVar[str] = "ExtractionRun"

    source_id: str | None = None
    processor: str | None = None
    processor_version: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    status: str | None = None


class RelationshipStateNode(GraphNodeModel):
    label: ClassVar[str] = "RelationshipState"

    status: str | None = None
    closeness: str | None = None
    source_kind: str | None = None
    is_current: bool | None = None


class ChangeRecordNode(GraphNodeModel):
    label: ClassVar[str] = "ChangeRecord"

    target_kind: str
    target_id: str
    target_label: str | None = None
    target_relationship_type: str | None = None
    field_path: str
    previous_value_json: str | None = None
    new_value_json: str | None = None
    changed_at: str | None = None
    changed_by: str | None = None
    reason: str | None = None


class MemoryLogNode(GraphNodeModel):
    label: ClassVar[str] = "MemoryLog"

    title: str | None = None
    log_text: str
    log_kind: str | None = None
    source_kind: str | None = None
    importance: str | None = None
    happened_at: str | None = None
    primary_host_target_id: str | None = None
    primary_host_target_label: str | None = None
    host_target_ids: list[str] = Field(default_factory=list)
    involved_target_ids: list[str] = Field(default_factory=list)
    relationship_context_target_ids: list[str] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)


class MediaAssetNode(GraphNodeModel):
    label: ClassVar[str] = "MediaAsset"

    media_type: str | None = None
    mime_type: str | None = None
    storage_uri: str | None = None
    storage_key: str | None = None
    checksum: str | None = None
    caption: str | None = None
    captured_at: str | None = None


class ContradictionRecordNode(GraphNodeModel):
    label: ClassVar[str] = "ContradictionRecord"

    contradiction_type: str | None = None
    severity: str | None = None
    status: str = "detected"
    reason: str | None = None
    detected_by: str | None = None
    detected_at: str | None = None
    resolved_at: str | None = None
    resolution_summary: str | None = None


class MergeRecordNode(GraphNodeModel):
    label: ClassVar[str] = "MergeRecord"

    merged_node_ids: list[str] = Field(default_factory=list)
    canonical_node_id: str
    reason: str | None = None
    merged_at: str | None = None
    performed_by: str | None = None
    status: str = "proposed"


NODE_MODEL_BY_LABEL: dict[str, type[GraphNodeModel]] = {
    PersonNode.label: PersonNode,
    EventNode.label: EventNode,
    PlaceNode.label: PlaceNode,
    OrganizationNode.label: OrganizationNode,
    ObjectNode.label: ObjectNode,
    AnimalNode.label: AnimalNode,
    SocialCircleNode.label: SocialCircleNode,
    TopicNode.label: TopicNode,
    SourceNode.label: SourceNode,
    ClaimNode.label: ClaimNode,
    PerceptionNode.label: PerceptionNode,
    RelationshipContextNode.label: RelationshipContextNode,
    ProfileMemoryNode.label: ProfileMemoryNode,
    ContactPointNode.label: ContactPointNode,
    ExternalReferenceNode.label: ExternalReferenceNode,
    ExtractionRunNode.label: ExtractionRunNode,
    RelationshipStateNode.label: RelationshipStateNode,
    ChangeRecordNode.label: ChangeRecordNode,
    MemoryLogNode.label: MemoryLogNode,
    MediaAssetNode.label: MediaAssetNode,
    ContradictionRecordNode.label: ContradictionRecordNode,
    MergeRecordNode.label: MergeRecordNode,
}


def node_model_for_label(label: str) -> type[GraphNodeModel]:
    validate_node_label(label)
    try:
        return NODE_MODEL_BY_LABEL[label]
    except KeyError as exc:
        raise GraphValidationError(f"No model registered for graph node label: {label}") from exc


class NodeUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class NodePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: dict[str, Any] = Field(default_factory=dict)


class GraphNodePresentation(BaseModel):
    """Backend-owned user-facing labels for graph clients."""

    title: str
    summary: str | None = None


class NodeSearchResult(BaseModel):
    label: str
    labels: list[str]
    properties: dict[str, Any]
    presentation: GraphNodePresentation | None = None

    @model_validator(mode="after")
    def _add_presentation(self) -> "NodeSearchResult":
        if self.presentation is None:
            self.presentation = GraphNodePresentation(
                title=_node_presentation_title(self.label, self.properties),
                summary=_node_presentation_summary(self.properties),
            )
        return self


def _node_presentation_title(label: str, properties: dict[str, Any]) -> str:
    for field in (
        "title",
        "display_name",
        "name",
        "label_text",
        "profile_key",
        "value",
        "caption",
        "text",
        "log_text",
        "description",
        "emotional_summary",
        "original_user_words",
    ):
        value = properties.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    aliases = properties.get("aliases")
    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                return alias.strip()
    return f"Unnamed {_readable_label(label)}"


def _node_presentation_summary(properties: dict[str, Any]) -> str | None:
    for field in ("description", "log_text", "emotional_summary", "original_user_words", "text"):
        value = properties.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _readable_label(label: str) -> str:
    words: list[str] = []
    current = ""
    for char in label:
        if char.isupper() and current and not current[-1].isupper():
            words.append(current)
            current = char
        else:
            current += char
    if current:
        words.append(current)
    return " ".join(words).lower() or "node"


class RelationshipUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    from_id: str
    to_id: str
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipStateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: dict[str, Any] = Field(default_factory=dict)
    make_current: bool = True


class RelationshipContextDetailResult(BaseModel):
    context: NodeSearchResult
    state_history: list[NodeSearchResult] = Field(default_factory=list)


class MemoryLogDetailResult(BaseModel):
    memory_log: NodeSearchResult
    hosts: list[NodeSearchResult] = Field(default_factory=list)
    involved: list[NodeSearchResult] = Field(default_factory=list)
    relationship_contexts: list[NodeSearchResult] = Field(default_factory=list)
    media_assets: list[NodeSearchResult] = Field(default_factory=list)
    relationships: list[RelationshipResult] = Field(default_factory=list)


class ChangeRecordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: dict[str, Any] = Field(default_factory=dict)


class LifecycleTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lifecycle_state: str
    reason: str | None = None
    changed_by: str = "system"
    source_ids: list[str] = Field(default_factory=list)
    extraction_run_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContradictionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: dict[str, Any] = Field(default_factory=dict)
    target_ids: list[str] = Field(default_factory=list)


class ContradictionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: dict[str, Any] = Field(default_factory=dict)


class MergeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_node_id: str
    merged_node_ids: list[str]
    reason: str | None = None
    performed_by: str = "system"
    source_ids: list[str] = Field(default_factory=list)
    extraction_run_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipResult(BaseModel):
    type: str
    from_id: str
    to_id: str
    properties: dict[str, Any]


class TimelineItem(BaseModel):
    id: str
    label: str
    title: str | None = None
    description: str | None = None
    time_value: str | None = None
    time_basis: str | None = None
    time_precision: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    emotional_summary: str | None = None
    original_user_words: str | None = None


class TimelineResult(BaseModel):
    seed: NodeSearchResult
    items: list[TimelineItem]


class EntityDetailResult(BaseModel):
    target: NodeSearchResult
    canonical: NodeSearchResult | None = None
    relationships: list[RelationshipResult] = Field(default_factory=list)
    perceptions: list[NodeSearchResult] = Field(default_factory=list)
    relationship_contexts: list[NodeSearchResult] = Field(default_factory=list)
    sources: list[NodeSearchResult] = Field(default_factory=list)
    changes: list[NodeSearchResult] = Field(default_factory=list)
    contradictions: list[NodeSearchResult] = Field(default_factory=list)
    merges: list[NodeSearchResult] = Field(default_factory=list)


class GraphViewNode(BaseModel):
    id: str
    label: str
    title: str | None = None
    description: str | None = None
    lifecycle_state: str | None = None
    privacy_level: str | None = None
    trust_level: str | None = None
    emotional_summary: str | None = None
    temporal_summary: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    display_metadata: dict[str, Any] = Field(default_factory=dict)


class GraphViewRelationship(BaseModel):
    id: str
    type: str
    from_id: str
    to_id: str
    description: str | None = None
    lifecycle_state: str | None = None
    emotional_summary: str | None = None
    temporal_summary: str | None = None


class GraphViewResult(BaseModel):
    seed_id: str
    nodes: list[GraphViewNode]
    relationships: list[GraphViewRelationship]


class MapViewResult(BaseModel):
    seed_id: str | None = None
    places: list[GraphViewNode] = Field(default_factory=list)
    events: list[GraphViewNode] = Field(default_factory=list)
    relationships: list[GraphViewRelationship] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)


class GraphContextPackage(BaseModel):
    target: dict[str, Any]
    current_facts: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    relationship_contexts: list[dict[str, Any]] = Field(default_factory=list)
    perceptions: list[dict[str, Any]] = Field(default_factory=list)
    matched_records: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    alias_map: dict[str, str] = Field(default_factory=dict)


class GraphAnalyticsItem(BaseModel):
    key: str
    count: int
    label: str | None = None


class GraphAnalyticsSummary(BaseModel):
    node_counts: dict[str, int] = Field(default_factory=dict)
    relationship_counts: dict[str, int] = Field(default_factory=dict)
    top_connected_nodes: list[GraphAnalyticsItem] = Field(default_factory=list)
    top_emotion_tags: list[GraphAnalyticsItem] = Field(default_factory=list)
    unresolved_contradictions: int = 0


class NeighborhoodResult(BaseModel):
    nodes: list[NodeSearchResult]
    relationships: list[RelationshipResult]


class AffectiveContextResult(BaseModel):
    target: NodeSearchResult
    direct_affective_fields: dict[str, Any]
    perceptions: list[NodeSearchResult]
    relationship_contexts: list[NodeSearchResult]
    affective_relationships: list[RelationshipResult]


class GraphRelationshipModel(GraphRelationshipBase):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


assert set(NODE_MODEL_BY_LABEL) == set(CORE_NODE_LABELS)
