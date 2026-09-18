"""Single source of truth for model-facing graph node mutations."""

from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel

from my_digital_brain.graph.models import (
    AnimalNodeCreate,
    AnimalNodePatch,
    EventNodeCreate,
    EventNodePatch,
    ObjectNodeCreate,
    ObjectNodePatch,
    OrganizationNodeCreate,
    OrganizationNodePatch,
    PersonNodeCreate,
    PersonNodePatch,
    PlaceNodeCreate,
    PlaceNodePatch,
    SocialCircleNodeCreate,
    SocialCircleNodePatch,
    TopicNodeCreate,
    TopicNodePatch,
)

type GraphWriteModel = type[BaseModel]


@dataclass(frozen=True)
class AgenticNodeMutationDefinition:
    label: str
    argument_name: str
    create_tool_name: str
    create_model: GraphWriteModel
    patch_tool_name: str
    patch_model: GraphWriteModel


AGENTIC_NODE_MUTATION_DEFINITIONS: tuple[AgenticNodeMutationDefinition, ...] = (
    AgenticNodeMutationDefinition("Person", "person", "create_person_node", PersonNodeCreate, "patch_person_node", PersonNodePatch),
    AgenticNodeMutationDefinition("Event", "event", "create_event_node", EventNodeCreate, "patch_event_node", EventNodePatch),
    AgenticNodeMutationDefinition("Place", "place", "create_place_node", PlaceNodeCreate, "patch_place_node", PlaceNodePatch),
    AgenticNodeMutationDefinition("Organization", "organization", "create_organization_node", OrganizationNodeCreate, "patch_organization_node", OrganizationNodePatch),
    AgenticNodeMutationDefinition("Object", "object", "create_object_node", ObjectNodeCreate, "patch_object_node", ObjectNodePatch),
    AgenticNodeMutationDefinition("Animal", "animal", "create_animal_node", AnimalNodeCreate, "patch_animal_node", AnimalNodePatch),
    AgenticNodeMutationDefinition("SocialCircle", "social_circle", "create_social_circle_node", SocialCircleNodeCreate, "patch_social_circle_node", SocialCircleNodePatch),
    AgenticNodeMutationDefinition("Topic", "topic", "create_topic_node", TopicNodeCreate, "patch_topic_node", TopicNodePatch),
)

AGENTIC_CREATABLE_NODE_LABELS = frozenset(
    definition.label for definition in AGENTIC_NODE_MUTATION_DEFINITIONS
)
AGENTIC_NODE_CREATION_TOOL_NAMES = tuple(
    definition.create_tool_name for definition in AGENTIC_NODE_MUTATION_DEFINITIONS
)
AGENTIC_NODE_PATCH_TOOL_NAMES = tuple(
    definition.patch_tool_name for definition in AGENTIC_NODE_MUTATION_DEFINITIONS
)


def agentic_node_mutation_definition(tool_name: str) -> AgenticNodeMutationDefinition:
    for definition in AGENTIC_NODE_MUTATION_DEFINITIONS:
        if tool_name in {definition.create_tool_name, definition.patch_tool_name}:
            return definition
    raise ValueError(f"No agentic node mutation definition exists for tool '{tool_name}'.")


def identity_gap_for_node_creation(label: str, payload: BaseModel) -> str | None:
    """Return the user-facing clarification reason for an unsafe durable identity."""

    if label != "Person":
        return None
    display_name = str(getattr(payload, "display_name", "") or "").strip()
    name_parts = [part for part in display_name.replace("-", " ").split() if part]
    if len(name_parts) >= 2:
        return None
    return (
        f"'{display_name}' has only one name component, so it is not a stable new Person identity. "
        "Ask the user for a surname, an established nickname mapping, or another distinguishing detail."
    )
