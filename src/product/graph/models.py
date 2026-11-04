"""Canonical typed contracts for semantic graph nodes."""

from enum import StrEnum
from typing import Literal

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
