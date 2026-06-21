from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.state import AgenticStateConfig
from my_digital_brain.agentic.tools.specs import (
    array_property,
    boolean_property,
    integer_property,
    object_property,
    optional_string_property,
    string_property,
    tool_spec,
)
from my_digital_brain.ai.models import ToolSpec


@dataclass(frozen=True)
class AgenticToolDefinition:
    name: str
    spec: ToolSpec
    allowed_states: frozenset[str]
    handler_key: str


class AgenticToolRegistry:
    def __init__(self, definitions: Iterable[AgenticToolDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}
        duplicates = [name for name in self._definitions if name.count("\0")]
        if duplicates:
            raise ValueError(f"Invalid tool names: {', '.join(sorted(duplicates))}")

    @property
    def definitions(self) -> dict[str, AgenticToolDefinition]:
        return dict(self._definitions)

    def get(self, name: str) -> AgenticToolDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise ValueError(f"Agentic tool is not registered: {name}") from exc

    def definitions_for_state(self, state_config: AgenticStateConfig) -> list[AgenticToolDefinition]:
        state_id = _state_value(state_config.state_id)
        forbidden = set(state_config.forbidden_tools)
        definitions: list[AgenticToolDefinition] = []
        for name in state_config.allowed_tools:
            if name in forbidden:
                raise ValueError(f"Tool '{name}' is both allowed and forbidden for {state_id}.")
            definition = self.get(name)
            if state_id not in definition.allowed_states:
                raise ValueError(f"Tool '{name}' is not registered for state {state_id}.")
            definitions.append(definition)
        return definitions

    def validate_state_configs(
        self,
        state_configs: dict[AgenticStateId, AgenticStateConfig],
    ) -> None:
        for state_config in state_configs.values():
            self.definitions_for_state(state_config)


def default_agentic_tool_registry() -> AgenticToolRegistry:
    return AgenticToolRegistry(_default_definitions())


def _definition(
    name: str,
    description: str,
    *,
    states: Iterable[AgenticStateId],
    handler_key: str | None = None,
    properties: dict[str, dict] | None = None,
    required: list[str] | None = None,
) -> AgenticToolDefinition:
    return AgenticToolDefinition(
        name=name,
        spec=tool_spec(name, description, properties=properties, required=required),
        allowed_states=frozenset(_state_value(state) for state in states),
        handler_key=handler_key or name,
    )


def _default_definitions() -> list[AgenticToolDefinition]:
    conversation_states = [AgenticStateId.CONVERSATION_ENTRY]
    memory_query_states = [AgenticStateId.MEMORY_QUERY]
    memory_ingestion_states = [AgenticStateId.MEMORY_INGESTION]
    memory_creation_states = [AgenticStateId.MEMORY_CREATION]
    graph_update_states = [AgenticStateId.GRAPH_UPDATE]
    contradiction_states = [AgenticStateId.CONTRADICTION_REVIEW]
    reasoning_states = [AgenticStateId.REASONING_CHECKPOINT]
    planning_states = [AgenticStateId.PLANNING_CHECKPOINT]

    return [
        _definition(
            "query_memory",
            "Future conversation-entry routing tool for answering from memory graph context.",
            states=conversation_states,
            properties={
                "question": string_property("User question to answer from memory."),
                "seed_id": optional_string_property("Known seed node id if already resolved."),
                "desired_view": optional_string_property("Requested view such as timeline or map."),
                "metadata": object_property("Additional low-noise query metadata."),
            },
            required=["question"],
        ),
        _definition(
            "ingest_memory",
            (
                "Future conversation-entry routing tool for processing the current "
                "message/history as memory. Takes no arguments; source content "
                "comes from the active frame history."
            ),
            states=conversation_states,
            properties={},
            required=[],
        ),
        _definition(
            "run_memory_creation",
            "Future child-frame starter for executing one memory creation plan action.",
            states=memory_ingestion_states,
            properties={
                "action_id": string_property("Plan action id to execute in memory_creation."),
                "metadata": object_property("Additional low-noise execution metadata."),
            },
            required=["action_id"],
        ),
        _definition(
            "update_memory_graph",
            (
                "Start a graph update subprocess when the user asks to update, "
                "correct, revise, or maintain memory graph state."
            ),
            states=[*memory_ingestion_states, *memory_creation_states],
            properties={
                "source_text": optional_string_property(
                    "Optional update/correction text. Use null when the child frame should derive it from history.",
                ),
                "guidelines": optional_string_property(
                    "Invocation guidelines from the caller. Use null if none.",
                ),
                "desired_work": optional_string_property(
                    "Conceptual work requested, such as create log, patch node, or update relationship.",
                ),
                "target_ids": array_property("Optional known graph target ids."),
                "source_refs": array_property("Optional source or media references."),
                "metadata": object_property("Additional low-noise request metadata."),
            },
            required=[],
        ),
        _definition(
            "request_user_clarification",
            (
                "Ask the user one to three direct, user-friendly clarification questions "
                "when the current state cannot continue safely. Questions must be "
                "short, specific, and free of internal summaries or schema language."
            ),
            states=[
                AgenticStateId.GRAPH_UPDATE,
                AgenticStateId.MEMORY_INGESTION,
                AgenticStateId.MEMORY_CREATION,
                AgenticStateId.CONTRADICTION_REVIEW,
                AgenticStateId.REASONING_CHECKPOINT,
                AgenticStateId.PLANNING_CHECKPOINT,
            ],
            properties={
                "reason": string_property(
                    "Internal reason user input is required before continuing. "
                    "Do not include this as user-facing copy.",
                ),
                "target_refs": array_property("Candidate refs, graph aliases, or targets involved."),
                "questions": _clarification_questions_property(),
            },
            required=["reason", "questions"],
        ),
        *_graph_read_definitions(
            memory_query_states,
            memory_ingestion_states,
            memory_creation_states,
            graph_update_states,
            contradiction_states,
            reasoning_states,
            planning_states,
        ),
        _definition(
            "resolve_graph_update_targets",
            "Resolve candidate graph targets for an update without mutating memory.",
            states=graph_update_states,
            properties={
                "query": string_property("Update text or target search query."),
                "target_ids": array_property("Known target ids supplied by the caller."),
                "limit": integer_property("Maximum candidate targets.", default=5, maximum=20),
            },
            required=["query"],
        ),
        _definition(
            "create_memory_log",
            "Create a MemoryLog and link it to host, involved, relationship context, and media targets.",
            states=[*graph_update_states, *memory_creation_states],
            properties={
                "log_text": string_property("Informational memory text to store."),
                "host_target_ids": array_property("Host graph node ids for this memory log."),
                "primary_host_target_id": optional_string_property(
                    "Primary host id when there are multiple hosts.",
                ),
                "involved_target_ids": array_property("Additional involved graph node ids."),
                "relationship_context_target_ids": array_property(
                    "RelationshipContext ids updated by this log.",
                ),
                "media_refs": array_property("MediaAsset ids or external media refs."),
                "log_kind": optional_string_property("Log kind, such as update or correction."),
                "source_kind": optional_string_property("Source kind, such as chat or user_update."),
                "happened_at": optional_string_property("Optional ISO event/update time."),
            },
            required=["log_text", "host_target_ids"],
        ),
        _definition(
            "create_graph_node",
            "Create a supported graph node using structurally validated JSON properties.",
            states=[*graph_update_states, *memory_creation_states],
            properties={
                "label": string_property("Supported graph node label."),
                "properties_json": string_property("JSON object containing node properties."),
            },
            required=["label", "properties_json"],
        ),
        _definition(
            "patch_graph_node",
            "Patch a supported graph node using structurally validated JSON properties.",
            states=graph_update_states,
            properties={
                "node_id": string_property("Target graph node id."),
                "properties_json": string_property("JSON object containing patch properties."),
            },
            required=["node_id", "properties_json"],
        ),
        _definition(
            "upsert_graph_relationship",
            "Create or update a supported non-destructive graph relationship.",
            states=[*graph_update_states, *memory_creation_states],
            properties={
                "relationship_type": string_property("Supported relationship type."),
                "from_id": string_property("Source graph node id."),
                "to_id": string_property("Target graph node id."),
                "properties_json": string_property("JSON object containing relationship properties."),
            },
            required=["relationship_type", "from_id", "to_id", "properties_json"],
        ),
        _definition(
            "create_relationship_state",
            "Create a RelationshipState for a RelationshipContext and optionally mark it current.",
            states=[*graph_update_states, *memory_creation_states],
            properties={
                "context_id": string_property("RelationshipContext node id."),
                "properties_json": string_property("JSON object containing state properties."),
                "make_current": boolean_property("Mark this state as current.", default=True),
            },
            required=["context_id", "properties_json", "make_current"],
        ),
    ]


def _graph_read_definitions(
    memory_query_states: list[AgenticStateId],
    memory_ingestion_states: list[AgenticStateId],
    memory_creation_states: list[AgenticStateId],
    graph_update_states: list[AgenticStateId],
    contradiction_states: list[AgenticStateId],
    reasoning_states: list[AgenticStateId],
    planning_states: list[AgenticStateId],
) -> list[AgenticToolDefinition]:
    return [
        _definition(
            "get_context_package",
            "Retrieve a low-noise LLM context package for a seed node.",
            states=[
                *memory_query_states,
                *memory_ingestion_states,
                *memory_creation_states,
                *graph_update_states,
                *reasoning_states,
                *planning_states,
            ],
            properties={
                "node_id": string_property("Seed node id."),
                "include_history": boolean_property("Include useful history.", default=True),
                "timeline_limit": integer_property("Timeline item limit.", default=20),
                "relationship_limit": integer_property("Relationship limit.", default=50),
            },
            required=["node_id"],
        ),
        _definition(
            "get_entity_detail",
            "Retrieve frontend-safe entity detail and evidence context.",
            states=[
                *memory_query_states,
                *memory_ingestion_states,
                *memory_creation_states,
                *graph_update_states,
                *reasoning_states,
                *planning_states,
            ],
            properties=_node_detail_properties(),
            required=["node_id"],
        ),
        _definition(
            "get_node_detail",
            "Retrieve node detail for contradiction review.",
            states=contradiction_states,
            handler_key="get_entity_detail",
            properties=_node_detail_properties(),
            required=["node_id"],
        ),
        _definition(
            "get_memories_involving_node",
            "Retrieve memories involving a seed node.",
            states=memory_query_states,
            properties=_node_detail_properties(),
            required=["node_id"],
        ),
        _definition(
            "get_timeline",
            "Retrieve timeline items for a seed node.",
            states=[*memory_query_states, *graph_update_states],
            properties={
                "node_id": string_property("Seed node id."),
                "from_time": optional_string_property("Optional ISO lower time bound."),
                "to_time": optional_string_property("Optional ISO upper time bound."),
                "include_history": boolean_property("Include history records.", default=False),
                "limit": integer_property("Timeline item limit.", default=100),
            },
            required=["node_id"],
        ),
        _definition(
            "get_neighborhood_view",
            "Retrieve a bounded graph neighborhood view.",
            states=[
                *memory_query_states,
                *memory_ingestion_states,
                *memory_creation_states,
                *contradiction_states,
                *graph_update_states,
                *reasoning_states,
                *planning_states,
            ],
            properties={
                "seed_id": string_property("Seed node id."),
                "depth": integer_property("Neighborhood depth.", default=1, maximum=3),
                "include_history": boolean_property("Include history records.", default=False),
                "include_archived": boolean_property("Include archived records.", default=False),
                "limit": integer_property("Maximum view nodes.", default=100),
            },
            required=["seed_id"],
        ),
        _definition(
            "get_map_view",
            "Retrieve map-ready places and events.",
            states=memory_query_states,
            properties={
                "seed_id": optional_string_property("Optional seed node id."),
                "city": optional_string_property("City filter."),
                "country": optional_string_property("Country filter."),
                "from_time": optional_string_property("Optional ISO lower time bound."),
                "to_time": optional_string_property("Optional ISO upper time bound."),
                "limit": integer_property("Maximum records.", default=100),
            },
        ),
        _definition(
            "get_target_evidence",
            "Retrieve source evidence for a graph target.",
            states=[
                *memory_query_states,
                *memory_ingestion_states,
                *memory_creation_states,
                *graph_update_states,
                *contradiction_states,
                *reasoning_states,
                *planning_states,
            ],
            properties={
                "target_id": string_property("Target node id."),
                "limit": integer_property("Maximum evidence records.", default=50),
            },
            required=["target_id"],
        ),
        _definition(
            "get_latest_contact_details",
            "Retrieve contact-point details connected to a person or organization.",
            states=memory_query_states,
            properties={
                "node_id": string_property("Person or organization node id."),
                "limit": integer_property("Maximum contact records.", default=20, maximum=50),
            },
            required=["node_id"],
        ),
        _definition(
            "get_change_records",
            "Retrieve change records for a node-like or relationship target.",
            states=contradiction_states,
            properties={
                "target_id": string_property("Target id."),
                "target_kind": optional_string_property("Target kind: node or relationship."),
                "limit": integer_property("Maximum change records.", default=50),
            },
            required=["target_id"],
        ),
        _definition(
            "get_relationship_state_history",
            "Retrieve state history for a RelationshipContext node.",
            states=contradiction_states,
            properties={
                "context_id": string_property("RelationshipContext node id."),
                "limit": integer_property("Maximum state records.", default=50),
            },
            required=["context_id"],
        ),
    ]


def _node_detail_properties() -> dict[str, dict]:
    return {
        "node_id": string_property("Target node id."),
        "include_history": boolean_property("Include history records.", default=False),
        "include_archived": boolean_property("Include archived records.", default=False),
        "limit": integer_property("Maximum records.", default=50),
    }


def _clarification_questions_property() -> dict:
    return {
        "type": "array",
        "description": (
            "One to three short, direct user-facing clarification questions. Do not "
            "include summaries, internal ids, schema labels, or process narration."
        ),
        "minItems": 1,
        "maxItems": 3,
        "items": {
            "type": "object",
            "properties": {
                "question": string_property("Short direct user-facing question addressed to the user. Use a question the UI can render verbatim, for example: Can you tell me where the barbeque happened?"),
                "options": {
                    "type": "array",
                    "description": "Concise suggested answers. Free text remains allowed.",
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": string_property("Short answer label."),
                            "description": optional_string_property(
                                "Optional explanation for this answer.",
                            ),
                            "recommended": boolean_property(
                                "Whether this is the recommended default option.",
                                default=False,
                            ),
                        },
                    },
                },
                "free_text_allowed": boolean_property(
                    "Whether the user may answer with free text.",
                    default=True,
                ),
                "required": boolean_property(
                    "Whether this question must be answered to continue.",
                    default=True,
                ),
                "selection_mode": string_property("Use single for v1 unless truly multiple."),
            },
        },
    }


def _state_value(state: AgenticStateId | str) -> str:
    return state.value if isinstance(state, AgenticStateId) else str(state)
