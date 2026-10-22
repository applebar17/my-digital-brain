"""Small semantic artifacts shared by configured agentic stages."""

from pydantic import BaseModel, Field


class ReasoningArtifact(BaseModel):
    """Concise decision-support observations from a configured reasoning stage."""

    summary: str = Field(description="Brief synthesis of the context relevant to the requested goal.")
    impacts: list[str] = Field(
        default_factory=list,
        description="Relevant effects or consequences that later work should account for.",
    )
    inconsistencies: list[str] = Field(
        default_factory=list,
        description="Material contradictions or mismatches found in the provided context.",
    )
    information_gaps: list[str] = Field(
        default_factory=list,
        description="Missing information that may affect the requested outcome.",
    )
    constraints_or_gates: list[str] = Field(
        default_factory=list,
        description="Constraints or decision gates that later work should respect.",
    )


class PlannedAction(BaseModel):
    """One semantic action proposed by a planning stage."""

    action: str = Field(description="Concise semantic action; not a backend function or tool name.")
    expected_outcome: str = Field(description="Observable result expected from this action.")
    risks: list[str] = Field(default_factory=list, description="Material risks, if any.")
    implications: list[str] = Field(
        default_factory=list,
        description="Relevant effects on later actions, context, or user-facing behavior.",
    )


class PlanArtifact(BaseModel):
    """Ordered, non-executable plan returned by a configured planning stage."""

    goal: str = Field(description="Goal addressed by the ordered planned actions.")
    planned_actions: list[PlannedAction] = Field(
        description="Semantic actions in intended order; this artifact grants no execution authority."
    )
