"""Explicit model-facing actions and results for semantic graph-node writes."""

from functools import reduce
from operator import or_
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from product.graph import (
    AnimalNodeCreateDTO,
    AnimalNodePatchDTO,
    EventNodeCreateDTO,
    EventNodePatchDTO,
    KnowledgeItemNodeCreateDTO,
    KnowledgeItemNodePatchDTO,
    NodeType,
    ObjectNodeCreateDTO,
    ObjectNodePatchDTO,
    OrganizationNodeCreateDTO,
    OrganizationNodePatchDTO,
    PersonNodeCreateDTO,
    PersonNodePatchDTO,
    PlaceNodeCreateDTO,
    PlaceNodePatchDTO,
    SocialCircleNodeCreateDTO,
    SocialCircleNodePatchDTO,
)


class GraphActionBaseDTO(BaseModel):
    """Fields shared by every model-requested semantic node action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_ref: str = Field(
        description="Exact candidate reference supplied in the active resolution context."
    )


class CreatePersonActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.PERSON] = Field(description="Create a Person node.")
    node: PersonNodeCreateDTO = Field(description="Explicit Person fields to persist.")


class CreateEventActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.EVENT] = Field(description="Create an Event node.")
    node: EventNodeCreateDTO = Field(description="Explicit Event fields to persist.")


class CreatePlaceActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.PLACE] = Field(description="Create a Place node.")
    node: PlaceNodeCreateDTO = Field(description="Explicit Place fields to persist.")


class CreateOrganizationActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.ORGANIZATION] = Field(
        description="Create an Organization node."
    )
    node: OrganizationNodeCreateDTO = Field(
        description="Explicit Organization fields to persist."
    )


class CreateObjectActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.OBJECT] = Field(description="Create an Object node.")
    node: ObjectNodeCreateDTO = Field(description="Explicit Object fields to persist.")


class CreateAnimalActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.ANIMAL] = Field(description="Create an Animal node.")
    node: AnimalNodeCreateDTO = Field(description="Explicit Animal fields to persist.")


class CreateSocialCircleActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.SOCIAL_CIRCLE] = Field(
        description="Create a SocialCircle node."
    )
    node: SocialCircleNodeCreateDTO = Field(
        description="Explicit SocialCircle fields to persist."
    )


class CreateKnowledgeItemActionDTO(GraphActionBaseDTO):
    operation: Literal["create"] = Field(description="Create a distinct node.")
    node_type: Literal[NodeType.KNOWLEDGE_ITEM] = Field(
        description="Create a KnowledgeItem node."
    )
    node: KnowledgeItemNodeCreateDTO = Field(
        description="Explicit KnowledgeItem fields to persist."
    )


class UpdateActionBaseDTO(GraphActionBaseDTO):
    """Shared target reference for explicit existing-node updates."""

    target_ref: str = Field(
        description="Exact existing node reference supplied in identity-match context."
    )


class UpdatePersonActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.PERSON] = Field(description="Update a Person node.")
    patch: PersonNodePatchDTO = Field(description="Explicit Person fields to enrich.")


class UpdateEventActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.EVENT] = Field(description="Update an Event node.")
    patch: EventNodePatchDTO = Field(description="Explicit Event fields to enrich.")


class UpdatePlaceActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.PLACE] = Field(description="Update a Place node.")
    patch: PlaceNodePatchDTO = Field(description="Explicit Place fields to enrich.")


class UpdateOrganizationActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.ORGANIZATION] = Field(
        description="Update an Organization node."
    )
    patch: OrganizationNodePatchDTO = Field(
        description="Explicit Organization fields to enrich."
    )


class UpdateObjectActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.OBJECT] = Field(description="Update an Object node.")
    patch: ObjectNodePatchDTO = Field(description="Explicit Object fields to enrich.")


class UpdateAnimalActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.ANIMAL] = Field(description="Update an Animal node.")
    patch: AnimalNodePatchDTO = Field(description="Explicit Animal fields to enrich.")


class UpdateSocialCircleActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.SOCIAL_CIRCLE] = Field(
        description="Update a SocialCircle node."
    )
    patch: SocialCircleNodePatchDTO = Field(
        description="Explicit SocialCircle fields to enrich."
    )


class UpdateKnowledgeItemActionDTO(UpdateActionBaseDTO):
    operation: Literal["update"] = Field(description="Update a supplied existing node.")
    node_type: Literal[NodeType.KNOWLEDGE_ITEM] = Field(
        description="Update a KnowledgeItem node."
    )
    patch: KnowledgeItemNodePatchDTO = Field(
        description="Explicit KnowledgeItem fields to enrich."
    )


GraphAction = (
    CreatePersonActionDTO
    | CreateEventActionDTO
    | CreatePlaceActionDTO
    | CreateOrganizationActionDTO
    | CreateObjectActionDTO
    | CreateAnimalActionDTO
    | CreateSocialCircleActionDTO
    | CreateKnowledgeItemActionDTO
    | UpdatePersonActionDTO
    | UpdateEventActionDTO
    | UpdatePlaceActionDTO
    | UpdateOrganizationActionDTO
    | UpdateObjectActionDTO
    | UpdateAnimalActionDTO
    | UpdateSocialCircleActionDTO
    | UpdateKnowledgeItemActionDTO
)

ACTION_MODELS_BY_NODE_TYPE: dict[NodeType, tuple[type[BaseModel], type[BaseModel]]] = {
    NodeType.PERSON: (CreatePersonActionDTO, UpdatePersonActionDTO),
    NodeType.EVENT: (CreateEventActionDTO, UpdateEventActionDTO),
    NodeType.PLACE: (CreatePlaceActionDTO, UpdatePlaceActionDTO),
    NodeType.ORGANIZATION: (CreateOrganizationActionDTO, UpdateOrganizationActionDTO),
    NodeType.OBJECT: (CreateObjectActionDTO, UpdateObjectActionDTO),
    NodeType.ANIMAL: (CreateAnimalActionDTO, UpdateAnimalActionDTO),
    NodeType.SOCIAL_CIRCLE: (CreateSocialCircleActionDTO, UpdateSocialCircleActionDTO),
    NodeType.KNOWLEDGE_ITEM: (
        CreateKnowledgeItemActionDTO,
        UpdateKnowledgeItemActionDTO,
    ),
}


class GraphActionResultDTO(BaseModel):
    """Successful graph action returned to the invoking state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_ref: str
    operation: Literal["create", "update"]
    node_type: NodeType
    node_ref: str = Field(description="Created or updated model-facing node reference.")
    display_name: str
    changed_fields: list[str]


def graph_action_input_model(node_types: list[NodeType]) -> type[BaseModel]:
    """Compile one input model from predeclared action variants for this batch."""
    selected: list[type[BaseModel]] = []
    for node_type in node_types:
        selected.extend(ACTION_MODELS_BY_NODE_TYPE[node_type])
    if not selected:
        raise ValueError("Graph action input requires at least one node type.")
    action_type = reduce(or_, selected)
    suffix = "_".join(node_type.value for node_type in node_types)
    return create_model(
        f"GraphActionInput_{suffix}",
        __config__=ConfigDict(extra="forbid"),
        action=(action_type, Field(description="One explicit typed graph-node action.")),
    )
