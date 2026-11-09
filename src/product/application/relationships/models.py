"""Model-safe bounded relationship-context read contracts."""

from pydantic import BaseModel, ConfigDict, Field

from product.application.references import ReferenceEntryDTO
from product.graph import RelationshipContextDTO, RelationshipStateDTO


class RelationshipStateProjectionDTO(BaseModel):
    """One model-safe relationship-state ref and its typed semantic fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: ReferenceEntryDTO
    state: RelationshipStateDTO


class RelationshipContextPacketDTO(BaseModel):
    """Bounded context packet for detail views or later model context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: ReferenceEntryDTO
    context: RelationshipContextDTO
    participants: list[ReferenceEntryDTO]
    memory_logs: list[ReferenceEntryDTO]
    states: list[RelationshipStateProjectionDTO] = Field(
        description="Bounded newest-first relationship-state history."
    )
