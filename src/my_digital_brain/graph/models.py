from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from my_digital_brain.core.models import GraphRecordBase, GraphRelationshipBase
from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.registry import CORE_NODE_LABELS, validate_node_label


class GraphNodeModel(GraphRecordBase):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=True)

    label: ClassVar[str]


class PersonNode(GraphNodeModel):
    label: ClassVar[str] = "Person"

    display_name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    known_since: str | None = None
    status: str | None = None


class EventNode(GraphNodeModel):
    label: ClassVar[str] = "Event"

    title: str | None = None
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
    circle_type: str | None = None
    source_kind: str | None = None


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


class NodeSearchResult(BaseModel):
    label: str
    labels: list[str]
    properties: dict[str, Any]


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
