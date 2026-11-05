"""Canonical typed contracts for semantic graph nodes."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class NodeType(StrEnum):
    """Semantic node categories supported by the target graph boundary."""

    PERSON = "person"
    EVENT = "event"
    PLACE = "place"
    ORGANIZATION = "organization"
    OBJECT = "object"
    ANIMAL = "animal"
    SOCIAL_CIRCLE = "social_circle"
    KNOWLEDGE_ITEM = "knowledge_item"


class KnowledgeItemKind(StrEnum):
    """Functional categories for standalone abstract information."""

    TOPIC = "topic"
    CONCEPT = "concept"
    IDEA = "idea"
    INSIGHT = "insight"
    REMINDER = "reminder"
    QUOTE = "quote"
    REFERENCE = "reference"
    OTHER = "other"


class IdentityMatchKind(StrEnum):
    """Strength of one deterministic identity-evidence match."""

    EXACT_NAME = "exact_name"
    EXACT_ALIAS = "exact_alias"
    NAME_TOKEN = "name_token"


GRAPH_LABEL_BY_NODE_TYPE: Mapping[NodeType, str] = {
    NodeType.PERSON: "Person",
    NodeType.EVENT: "Event",
    NodeType.PLACE: "Place",
    NodeType.ORGANIZATION: "Organization",
    NodeType.OBJECT: "Object",
    NodeType.ANIMAL: "Animal",
    NodeType.SOCIAL_CIRCLE: "SocialCircle",
    NodeType.KNOWLEDGE_ITEM: "KnowledgeItem",
}


class NodeCreateDTO(BaseModel):
    """Fields with the same persistence meaning for every semantic node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: NodeType = Field(
        description="Semantic node category selecting the concrete node contract."
    )
    description: str | None = Field(
        description="Concise user-meaningful description when supported by the source."
    )
    aliases: list[str] = Field(
        description="Source-supported alternate names or phrases for this node."
    )


class PersonNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one person node."""

    node_type: Literal[NodeType.PERSON] = Field(description="Person node.")
    display_name: str = Field(description="Best human-readable name for the person.")
    given_name: str | None = Field(description="Person's given name when explicitly available.")
    surname: str | None = Field(description="Person's surname when explicitly available.")
    known_since: str | None = Field(
        description="Readable information about when the owner came to know the person."
    )


class EventNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one event node."""

    node_type: Literal[NodeType.EVENT] = Field(description="Event node.")
    title: str = Field(description="Concise human-readable title for the event.")
    started_at: str | None = Field(description="Known event start date, time, or range.")
    ended_at: str | None = Field(description="Known event end date or time.")
    time_precision: str | None = Field(
        description="Available precision of the event timing."
    )
    organizer_hint: str | None = Field(
        description=(
            "Source wording that may later support organizer resolution; it is not an "
            "authoritative graph relationship."
        )
    )


class PlaceNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one place node."""

    node_type: Literal[NodeType.PLACE] = Field(description="Place node.")
    name: str = Field(description="Human-readable name of the place.")
    address: str | None = Field(description="Street or venue address when available.")
    city: str | None = Field(description="City when available.")
    region: str | None = Field(description="Region or state when available.")
    country: str | None = Field(description="Country when available.")
    place_precision: str | None = Field(
        description="Available granularity such as country, city, venue, or address."
    )
    owner_hint: str | None = Field(
        description=(
            "Source wording that may later support place-owner resolution; it is not an "
            "authoritative graph relationship."
        )
    )


class OrganizationNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one organization node."""

    node_type: Literal[NodeType.ORGANIZATION] = Field(description="Organization node.")
    name: str = Field(description="Human-readable organization or group name.")
    domain: str | None = Field(description="Business or activity domain when available.")


class ObjectNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one meaningful object node."""

    node_type: Literal[NodeType.OBJECT] = Field(description="Object node.")
    name: str = Field(description="Human-readable name of the meaningful object.")
    category: str | None = Field(description="Object category when supported by the source.")
    owner_hint: str | None = Field(
        description=(
            "Source wording that may later support ownership resolution; it is not an "
            "authoritative ownership relationship."
        )
    )


class AnimalNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one meaningful animal node."""

    node_type: Literal[NodeType.ANIMAL] = Field(description="Animal node.")
    name: str = Field(description="Animal name or best human-readable mention.")
    species: str | None = Field(description="Animal species when known.")
    breed: str | None = Field(description="Animal breed when known.")
    sex: str | None = Field(description="Animal sex when explicitly stated.")
    owner_hint: str | None = Field(
        description=(
            "Source wording that may later support owner or carer resolution; it is not "
            "an authoritative graph relationship."
        )
    )


class SocialCircleNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one user-perceived social circle."""

    node_type: Literal[NodeType.SOCIAL_CIRCLE] = Field(description="Social-circle node.")
    name: str = Field(description="Human-readable name of the social circle.")
    circle_type: str | None = Field(
        description="General grouping such as family, friends, colleagues, or neighbors."
    )


class KnowledgeItemNodeCreateDTO(NodeCreateDTO):
    """Typed creation fields for one standalone knowledge item."""

    node_type: Literal[NodeType.KNOWLEDGE_ITEM] = Field(description="Knowledge-item node.")
    knowledge_kind: KnowledgeItemKind = Field(
        description="Functional category of the standalone knowledge item."
    )
    title: str = Field(description="Concise title suitable for retrieval and display.")
    content: str = Field(description="The abstract information retained for future use.")
    attribution: str | None = Field(
        description="Who said or originated the item when relevant and available."
    )
    reminder_at: str | None = Field(
        description="When the reminder matters, without implying scheduled notification."
    )


NodeCreate = (
    PersonNodeCreateDTO
    | EventNodeCreateDTO
    | PlaceNodeCreateDTO
    | OrganizationNodeCreateDTO
    | ObjectNodeCreateDTO
    | AnimalNodeCreateDTO
    | SocialCircleNodeCreateDTO
    | KnowledgeItemNodeCreateDTO
)

NODE_CREATE_MODEL_BY_TYPE: Mapping[NodeType, type[NodeCreateDTO]] = {
    NodeType.PERSON: PersonNodeCreateDTO,
    NodeType.EVENT: EventNodeCreateDTO,
    NodeType.PLACE: PlaceNodeCreateDTO,
    NodeType.ORGANIZATION: OrganizationNodeCreateDTO,
    NodeType.OBJECT: ObjectNodeCreateDTO,
    NodeType.ANIMAL: AnimalNodeCreateDTO,
    NodeType.SOCIAL_CIRCLE: SocialCircleNodeCreateDTO,
    NodeType.KNOWLEDGE_ITEM: KnowledgeItemNodeCreateDTO,
}


class NodePatchDTO(BaseModel):
    """Fields with shared update semantics for every semantic node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: NodeType = Field(description="Semantic type of the existing node to update.")
    description: str | None = Field(
        description="Replacement grounded description, or null to leave it unchanged."
    )
    aliases_to_add: list[str] = Field(
        description="Source-supported aliases to add without removing existing aliases."
    )


class PersonNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.PERSON] = Field(description="Person node update.")
    display_name: str | None = Field(description="Replacement readable name, or null.")
    given_name: str | None = Field(description="Replacement given name, or null.")
    surname: str | None = Field(description="Replacement surname, or null.")
    known_since: str | None = Field(description="Replacement known-since information, or null.")


class EventNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.EVENT] = Field(description="Event node update.")
    title: str | None = Field(description="Replacement event title, or null.")
    started_at: str | None = Field(description="Replacement event start, or null.")
    ended_at: str | None = Field(description="Replacement event end, or null.")
    time_precision: str | None = Field(description="Replacement time precision, or null.")
    organizer_hint: str | None = Field(description="Replacement organizer cue, or null.")


class PlaceNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.PLACE] = Field(description="Place node update.")
    name: str | None = Field(description="Replacement place name, or null.")
    address: str | None = Field(description="Replacement address, or null.")
    city: str | None = Field(description="Replacement city, or null.")
    region: str | None = Field(description="Replacement region, or null.")
    country: str | None = Field(description="Replacement country, or null.")
    place_precision: str | None = Field(description="Replacement place precision, or null.")
    owner_hint: str | None = Field(description="Replacement place-owner cue, or null.")


class OrganizationNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.ORGANIZATION] = Field(description="Organization node update.")
    name: str | None = Field(description="Replacement organization name, or null.")
    domain: str | None = Field(description="Replacement organization domain, or null.")


class ObjectNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.OBJECT] = Field(description="Object node update.")
    name: str | None = Field(description="Replacement object name, or null.")
    category: str | None = Field(description="Replacement object category, or null.")
    owner_hint: str | None = Field(description="Replacement ownership cue, or null.")


class AnimalNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.ANIMAL] = Field(description="Animal node update.")
    name: str | None = Field(description="Replacement animal name, or null.")
    species: str | None = Field(description="Replacement species, or null.")
    breed: str | None = Field(description="Replacement breed, or null.")
    sex: str | None = Field(description="Replacement sex, or null.")
    owner_hint: str | None = Field(description="Replacement owner or carer cue, or null.")


class SocialCircleNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.SOCIAL_CIRCLE] = Field(description="Social-circle update.")
    name: str | None = Field(description="Replacement social-circle name, or null.")
    circle_type: str | None = Field(description="Replacement circle category, or null.")


class KnowledgeItemNodePatchDTO(NodePatchDTO):
    node_type: Literal[NodeType.KNOWLEDGE_ITEM] = Field(description="Knowledge-item update.")
    knowledge_kind: KnowledgeItemKind | None = Field(
        description="Replacement knowledge category, or null."
    )
    title: str | None = Field(description="Replacement knowledge-item title, or null.")
    content: str | None = Field(description="Replacement retained content, or null.")
    attribution: str | None = Field(description="Replacement attribution, or null.")
    reminder_at: str | None = Field(description="Replacement reminder timing, or null.")


NodePatch = (
    PersonNodePatchDTO
    | EventNodePatchDTO
    | PlaceNodePatchDTO
    | OrganizationNodePatchDTO
    | ObjectNodePatchDTO
    | AnimalNodePatchDTO
    | SocialCircleNodePatchDTO
    | KnowledgeItemNodePatchDTO
)


class StoredNodeDTO(BaseModel):
    """Trusted persisted node returned by the graph repository boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str = Field(description="Backend graph identifier kept outside model context.")
    node: NodeCreate = Field(description="Typed semantic properties stored for this node.")


class IdentityMatchDTO(BaseModel):
    """Trusted backend identity evidence before model-safe reference projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str = Field(description="Backend identifier kept outside model context.")
    node: NodeCreate = Field(description="Typed existing node matching the candidate search.")
    match_kind: IdentityMatchKind = Field(description="Deterministic match classification.")


class IdentityLookupResultDTO(BaseModel):
    """Bounded same-type identity evidence returned for one candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    matches: list[IdentityMatchDTO] = Field(description="Ordered deterministic match evidence.")


class GraphNodeRepository(Protocol):
    """Owner-scoped persistence operations required by node resolution."""

    def search_nodes(
        self,
        owner_id: str,
        node_type: NodeType,
        terms: list[str],
        *,
        limit: int,
    ) -> list[StoredNodeDTO]: ...

    def get_node(
        self,
        owner_id: str,
        backend_id: str,
        node_type: NodeType,
    ) -> StoredNodeDTO: ...

    def create_node(self, owner_id: str, node: NodeCreate) -> StoredNodeDTO: ...

    def update_node(
        self,
        owner_id: str,
        backend_id: str,
        node: NodeCreate,
    ) -> StoredNodeDTO: ...


class GraphQueryExecutor(Protocol):
    """Minimal Cypher execution boundary implemented by the configured graph client."""

    def execute_read(
        self,
        cypher: str,
        parameters: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]: ...

    def execute_write(
        self,
        cypher: str,
        parameters: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]: ...
