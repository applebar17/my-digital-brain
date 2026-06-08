from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.drafts import ClarificationRequestDraft
from my_digital_brain.ingestion.ontology import LLMEntityType


class IngestionReasoningCheckpointDraft(IngestionModel):
    """Lightweight ingestion reasoning notes for later planning steps."""

    summary: str = Field(description="Concise reasoning summary for this source/context.")
    entity_notes: list[str] = Field(
        default_factory=list,
        description="Notes about possible entities, including what should or should not be a node.",
    )
    alias_notes: list[str] = Field(
        default_factory=list,
        description="Notes about aliases, nicknames, and mention variants as resolution hints.",
    )
    relationship_notes: list[str] = Field(
        default_factory=list,
        description="Notes about relationships or relationship context suggested by the source.",
    )
    duplicate_notes: list[str] = Field(
        default_factory=list,
        description="Notes about possible duplicates or ambiguous identity matches.",
    )
    node_vs_detail_notes: list[str] = Field(
        default_factory=list,
        description="Notes distinguishing standalone nodes from details on existing nodes.",
    )
    user_owner_notes: list[str] = Field(
        default_factory=list,
        description="Notes about user-specific ownership or perspective when relevant.",
    )
    context_gaps: list[str] = Field(
        default_factory=list,
        description="Missing context that may weaken extraction or planning.",
    )
    clarification_candidates: list[ClarificationRequestDraft] = Field(
        default_factory=list,
        description="Clarifications that may be needed before safe ingestion.",
    )
    next_context_summary: str | None = Field(
        default=None,
        description="Compact carry-forward summary for the next planning transform.",
    )

    @model_validator(mode="after")
    def _validate_useful_signal(self) -> "IngestionReasoningCheckpointDraft":
        if not self.summary.strip():
            raise ValueError("Ingestion reasoning checkpoint requires a summary.")
        if not (
            self.entity_notes
            or self.alias_notes
            or self.relationship_notes
            or self.duplicate_notes
            or self.node_vs_detail_notes
            or self.user_owner_notes
            or self.context_gaps
            or self.clarification_candidates
            or self.next_context_summary
        ):
            raise ValueError("Ingestion reasoning checkpoint requires at least one note.")
        return self


class EntityIngestionActionDraft(IngestionModel):
    action_ref: str = Field(description="Planner-scoped action handle such as ENTITY_ACTION_001.")
    goal: str = Field(description="Short goal for the entity extraction or resolution action.")
    mention_text: str | None = Field(
        default=None,
        description="Source mention or normalized phrase this entity action concerns.",
    )
    suggested_entity_type: LLMEntityType | None = Field(
        default=None,
        description="Suggested entity type when the source supports it.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description=(
            "Alias or nickname hints for extraction and resolution. They do not define "
            "node identity and are not automatically writable node properties."
        ),
    )
    evidence_text: str | None = Field(
        default=None,
        description="Source wording or compact context supporting this entity action.",
    )
    context_refs: list[str] = Field(
        default_factory=list,
        description="Graph aliases or local refs this action should consider.",
    )
    notes: str | None = Field(
        default=None,
        description="Short planner note for the later entity extraction step.",
    )


class EntityIngestionPlanDraft(IngestionModel):
    reason: str | None = Field(
        default=None,
        description="Concise reason for the selected entity plan.",
    )
    actions: list[EntityIngestionActionDraft] = Field(
        default_factory=list,
        description="Simple entity actions to execute or hand off.",
    )
    clarification: ClarificationRequestDraft | None = Field(
        default=None,
        description="Blocking clarification required before entity extraction can continue.",
    )
    context_gaps: list[str] = Field(
        default_factory=list,
        description="Missing context that should be retrieved before entity extraction.",
    )

    @model_validator(mode="after")
    def _validate_has_next_step(self) -> "EntityIngestionPlanDraft":
        if not (self.actions or self.clarification or self.context_gaps):
            raise ValueError(
                "Entity ingestion plan requires actions, clarification, or context gaps."
            )
        return self


RelationshipStorageShape = Literal[
    "direct_relationship",
    "relationship_context",
    "perception",
    "claim",
    "metadata_note",
    "defer",
]


class MissingEntityRequiredDraft(IngestionModel):
    """Structured blocker used to re-plan missing endpoint extraction."""

    missing_ref: str = Field(
        description="Planner-local ref for the missing endpoint, such as MISSING_ENTITY_001.",
    )
    reason: str = Field(description="Why this missing entity is required.")
    mention_text: str | None = Field(
        default=None,
        description="Source mention or normalized phrase for the missing entity.",
    )
    suggested_entity_type: LLMEntityType | None = Field(
        default=None,
        description="Suggested entity type when the source supports it.",
    )
    needed_for_relationship_ref: str = Field(
        description="Relationship action ref blocked by this missing entity.",
    )
    relationship_goal: str = Field(
        description="Relationship goal to resume after the missing entity is resolved.",
    )
    relationship_endpoint_role: Literal["from", "to", "either"] = Field(
        default="either",
        description="Endpoint role the missing entity should fill when planning resumes.",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Source wording that supports both the missing entity and relationship need.",
    )
    entity_planning_guidance: str | None = Field(
        default=None,
        description="Compact guidance to pass into the missing-entity planning step.",
    )
    relationship_resume_guidance: str | None = Field(
        default=None,
        description="Compact guidance for resuming blocked relationship planning.",
    )


class RelationshipIngestionActionDraft(IngestionModel):
    action_ref: str = Field(description="Planner-scoped action handle such as REL_ACTION_001.")
    goal: str = Field(description="Short goal for the relationship action.")
    from_ref: str | None = Field(
        default=None,
        description="Resolved entity ref, staged entity ref, graph alias, or missing ref.",
    )
    to_ref: str | None = Field(
        default=None,
        description="Resolved entity ref, staged entity ref, graph alias, or missing ref.",
    )
    relationship_intent: str = Field(
        description="Plain-language relationship intent to preserve for extraction.",
    )
    storage_shape: RelationshipStorageShape = Field(
        default="direct_relationship",
        description="Lightweight storage shape recommendation for later extraction.",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Source wording or compact context supporting this relationship action.",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Entity action refs or missing refs required before this action can run.",
    )
    notes: str | None = Field(
        default=None,
        description="Short planner note for the later relationship extraction step.",
    )


class RelationshipIngestionPlanDraft(IngestionModel):
    reason: str | None = Field(
        default=None,
        description="Concise reason for the selected relationship plan.",
    )
    actions: list[RelationshipIngestionActionDraft] = Field(
        default_factory=list,
        description="Simple relationship actions to execute or hand off.",
    )
    missing_entities: list[MissingEntityRequiredDraft] = Field(
        default_factory=list,
        description="Missing endpoints that must be entity-planned before blocked relationships resume.",
    )
    clarification: ClarificationRequestDraft | None = Field(
        default=None,
        description="Blocking clarification required before relationship extraction can continue.",
    )
    context_gaps: list[str] = Field(
        default_factory=list,
        description="Missing context that should be retrieved before relationship extraction.",
    )

    @model_validator(mode="after")
    def _validate_has_next_step(self) -> "RelationshipIngestionPlanDraft":
        if not (self.actions or self.missing_entities or self.clarification or self.context_gaps):
            raise ValueError(
                "Relationship ingestion plan requires actions, missing entities, "
                "clarification, or context gaps."
            )
        return self
