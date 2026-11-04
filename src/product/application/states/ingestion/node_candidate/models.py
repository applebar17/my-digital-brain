"""Typed input and candidate output contracts for node detection."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from product.application.references import OwnerContextDTO, ReferenceEntryDTO
from product.application.states.ingestion.reasoning import IngestionReasoningResultDTO
from product.graph import KnowledgeItemKind, NodeType


class NodeCandidateStateInputDTO(BaseModel):
    """Reasoning and model-safe context supplied to candidate generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reasoning: IngestionReasoningResultDTO = Field(
        description="Completed semantic interpretation of the inherited conversation."
    )
    owner: OwnerContextDTO = Field(
        description="Safe identity projection of the current memory owner."
    )
    known_references: list[ReferenceEntryDTO] = Field(
        description="Relevant model-facing references available for recognition context."
    )


class NodeCandidateDTO(BaseModel):
    """Fields shared by semantic candidates before lookup or persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: NodeType = Field(
        description="Candidate category used to select the explicit subtype contract."
    )
    description: str | None = Field(
        description="Concise user-meaningful description when the mention supports one."
    )
    aliases: list[str] = Field(
        description="Mentioned alternate names or phrases; excludes speculative aliases."
    )
    identity_gaps: list[str] = Field(
        description="Missing details that may matter during later identity resolution."
    )


class PersonCandidateDTO(NodeCandidateDTO):
    """One human mentioned in the inherited conversation."""

    node_type: Literal[NodeType.PERSON] = Field(description="Person candidate.")
    display_name: str = Field(description="Best readable name supported by the conversation.")
    given_name: str | None = Field(description="Given name when explicitly available.")
    surname: str | None = Field(description="Surname when explicitly available.")
    known_since: str | None = Field(description="Readable known-since information when stated.")


class EventCandidateDTO(NodeCandidateDTO):
    """One occurrence with useful temporal or participation meaning."""

    node_type: Literal[NodeType.EVENT] = Field(description="Event candidate.")
    title: str = Field(description="Concise readable title for the event.")
    started_at: str | None = Field(description="Stated start date, time, or readable range.")
    ended_at: str | None = Field(description="Stated end date or time when available.")
    time_precision: str | None = Field(description="Available precision of the event timing.")
    organizer_hint: str | None = Field(
        description="Readable event-organizer cue from the conversation, not an object reference."
    )


class PlaceCandidateDTO(NodeCandidateDTO):
    """One physical or logical location."""

    node_type: Literal[NodeType.PLACE] = Field(description="Place candidate.")
    name: str = Field(description="Readable place name supported by the conversation.")
    address: str | None = Field(description="Street or venue address when stated.")
    city: str | None = Field(description="City when stated or inherent in the place mention.")
    region: str | None = Field(description="Region or state when available.")
    country: str | None = Field(description="Country when available.")
    place_precision: str | None = Field(
        description="Available granularity such as country, city, venue, or address."
    )
    owner_hint: str | None = Field(
        description="Readable place-owner cue from the conversation, not an object reference."
    )


class OrganizationCandidateDTO(NodeCandidateDTO):
    """One formal or informal organization, institution, team, or group."""

    node_type: Literal[NodeType.ORGANIZATION] = Field(
        description="Organization candidate."
    )
    name: str = Field(description="Readable organization or group name.")
    domain: str | None = Field(description="Business or activity domain when stated.")


class ObjectCandidateDTO(NodeCandidateDTO):
    """One meaningful physical or digital object."""

    node_type: Literal[NodeType.OBJECT] = Field(description="Object candidate.")
    name: str = Field(description="Readable name of the meaningful object.")
    category: str | None = Field(description="Object category when useful and supported.")
    owner_hint: str | None = Field(
        description="Readable ownership cue from the conversation, not an object reference."
    )


class AnimalCandidateDTO(NodeCandidateDTO):
    """One meaningful animal, including a pet."""

    node_type: Literal[NodeType.ANIMAL] = Field(description="Animal candidate.")
    name: str = Field(description="Animal name or best readable mention.")
    species: str | None = Field(description="Species when known.")
    breed: str | None = Field(description="Breed when known.")
    sex: str | None = Field(description="Sex when stated.")
    owner_hint: str | None = Field(
        description="Readable owner or carer cue, not an object reference."
    )


class SocialCircleCandidateDTO(NodeCandidateDTO):
    """One user-perceived social grouping."""

    node_type: Literal[NodeType.SOCIAL_CIRCLE] = Field(
        description="Social-circle candidate."
    )
    name: str = Field(description="Readable name of the user-perceived social grouping.")
    circle_type: str | None = Field(
        description="General grouping such as family, friends, colleagues, or neighbors."
    )


class KnowledgeItemCandidateDTO(NodeCandidateDTO):
    """One standalone abstract item retained for future use or recall."""

    node_type: Literal[NodeType.KNOWLEDGE_ITEM] = Field(
        description="Knowledge-item candidate."
    )
    knowledge_kind: KnowledgeItemKind = Field(
        description="Functional category of the standalone knowledge item."
    )
    title: str = Field(description="Concise title suitable for later retrieval and display.")
    content: str = Field(description="The idea, insight, reminder, quote, or reference content.")
    attribution: str | None = Field(
        description="Who said or originated the item when relevant and available."
    )
    reminder_at: str | None = Field(
        description="When the reminder matters, without implying scheduled notification."
    )


NodeCandidate = (
    PersonCandidateDTO
    | EventCandidateDTO
    | PlaceCandidateDTO
    | OrganizationCandidateDTO
    | ObjectCandidateDTO
    | AnimalCandidateDTO
    | SocialCircleCandidateDTO
    | KnowledgeItemCandidateDTO
)


class NodeCandidateSetDTO(BaseModel):
    """Complete semantic candidate inventory returned by one state call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: list[NodeCandidate] = Field(
        description=(
            "Typed candidates supported by the inherited conversation; an empty list means "
            "that no durable semantic node candidate was identified."
        )
    )

    def present_types(self) -> set[NodeType]:
        """Derive candidate kinds for later state/tool configuration."""
        return {candidate.node_type for candidate in self.candidates}
