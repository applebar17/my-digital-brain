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
    conversation_states = [
        AgenticStateId.CONVERSATION_ENTRY,
        AgenticStateId.PENDING_PROCESS_REVIEW,
    ]
    memory_query_states = [AgenticStateId.MEMORY_QUERY]
    correction_states = [AgenticStateId.CORRECTION_INTAKE]
    contradiction_states = [AgenticStateId.CONTRADICTION_REVIEW]

    return [
        _definition(
            "start_memory_ingestion",
            "Start a memory ingestion subprocess from text or media-derived text.",
            states=conversation_states,
            properties={
                "source_text": string_property("Memory text or transcript to ingest."),
                "source_refs": array_property("Optional source or media references."),
                "pending_process_policy": optional_string_property(
                    "Policy for an active pending process, such as pause or cancel.",
                ),
                "metadata": object_property("Additional low-noise request metadata."),
            },
            required=["source_text"],
        ),
        _definition(
            "query_memory_context",
            "Retrieve memory context for a user question.",
            states=[*conversation_states, AgenticStateId.MEMORY_QUERY],
            properties={
                "question": string_property("User question to answer from memory."),
                "seed_id": optional_string_property("Known seed node id if already resolved."),
                "desired_view": optional_string_property("Requested view such as timeline or map."),
                "metadata": object_property("Additional low-noise query metadata."),
            },
            required=["question"],
        ),
        _definition(
            "propose_memory_correction",
            "Propose a correction to existing memory without applying it.",
            states=conversation_states,
            properties={
                "correction_text": string_property("User correction text."),
                "target_id": optional_string_property("Known target node id if available."),
                "metadata": object_property("Additional low-noise correction metadata."),
            },
            required=["correction_text"],
        ),
        _definition(
            "get_conversation_status",
            "Return current conversation and pending-process status.",
            states=[AgenticStateId.CONVERSATION_ENTRY],
            properties={"metadata": object_property("Optional status metadata.")},
        ),
        _definition(
            "cancel_pending_process",
            "Cancel an active pending process when the user explicitly asks.",
            states=conversation_states,
            properties={
                "pending_process_id": optional_string_property("Pending process id to cancel."),
                "reason": optional_string_property("User-facing cancellation reason."),
            },
        ),
        _definition(
            "resume_pending_process",
            "Resume a pending process with the user's latest reply.",
            states=[AgenticStateId.PENDING_PROCESS_REVIEW],
            properties={
                "pending_process_id": optional_string_property("Pending process id to resume."),
                "user_reply": string_property("Latest user reply."),
            },
            required=["user_reply"],
        ),
        _definition(
            "pause_pending_process",
            "Pause a pending process without forcing the current message into it.",
            states=[AgenticStateId.PENDING_PROCESS_REVIEW],
            properties={
                "pending_process_id": optional_string_property("Pending process id to pause."),
                "reason": optional_string_property("Why the process should remain paused."),
            },
        ),
        _definition(
            "request_graph_context_expansion",
            "Request compact graph context expansion for ingestion planning.",
            states=[AgenticStateId.MEMORY_INGESTION_PLANNING],
            properties={
                "query": optional_string_property("Search text for additional context."),
                "seed_id": optional_string_property("Seed node id for context package retrieval."),
                "limit": integer_property("Maximum records to retrieve.", default=10, maximum=50),
            },
        ),
        _definition(
            "request_contradiction_review",
            "Ask the contradiction review state to inspect an agent-inferred ambiguity or conflict.",
            states=[AgenticStateId.MEMORY_INGESTION_PLANNING],
            properties={
                "agent_doubt": string_property(
                    "Grounded explanation of the ambiguity or contradiction the agent sees.",
                ),
                "proposed_write_ref": optional_string_property(
                    "Optional proposed write or candidate reference involved in the doubt.",
                ),
                "proposed_write": object_property(
                    "Optional proposed write or candidate payload involved in the doubt.",
                ),
                "affected_entity_refs": array_property(
                    "Entity aliases or ids involved in the doubt.",
                ),
                "affected_relationship_refs": array_property(
                    "Relationship aliases or ids involved in the doubt.",
                ),
                "source_refs": array_property("Source refs supporting the doubt."),
                "metadata": object_property("Additional low-noise contradiction metadata."),
            },
            required=["agent_doubt"],
        ),
        _definition(
            "submit_extraction_plan",
            "Submit the final validated ExtractionPlan for backend ingestion execution.",
            states=[AgenticStateId.MEMORY_INGESTION_PLANNING],
            properties={
                "plan": object_property(
                    "ExtractionPlan payload matching the ingestion contract.",
                ),
            },
            required=["plan"],
        ),
        *_graph_read_definitions(memory_query_states, correction_states, contradiction_states),
        _definition(
            "resolve_correction_target",
            "Resolve the graph target for a correction without mutating memory.",
            states=correction_states,
            properties={
                "correction_text": string_property("Correction text to resolve."),
                "target_id": optional_string_property("Known target id if supplied."),
                "limit": integer_property("Maximum candidate targets.", default=5, maximum=20),
            },
            required=["correction_text"],
        ),
        _definition(
            "build_correction_proposal",
            "Build a confirmation-aware correction proposal without applying it.",
            states=correction_states,
            properties={
                "correction_text": string_property("Correction text from the user."),
                "target_id": string_property("Resolved target id."),
                "target_label": optional_string_property("Resolved target label."),
                "field_path": optional_string_property("Field or path to update."),
                "current_value": object_property("Current value snapshot."),
                "proposed_value": object_property("Proposed value snapshot."),
                "reason": string_property("Why this correction is proposed."),
                "risk_level": optional_string_property("Risk level: low, medium, or high."),
            },
            required=["correction_text", "target_id", "reason"],
        ),
        _definition(
            "request_user_confirmation",
            "Create a confirmation handoff for a risky proposal.",
            states=correction_states,
            properties={
                "question": string_property("Natural confirmation question for the user."),
                "proposal": object_property("Correction proposal payload."),
                "target_refs": array_property("Target references involved in the proposal."),
            },
            required=["question", "proposal"],
        ),
    ]


def _graph_read_definitions(
    memory_query_states: list[AgenticStateId],
    correction_states: list[AgenticStateId],
    contradiction_states: list[AgenticStateId],
) -> list[AgenticToolDefinition]:
    return [
        _definition(
            "get_context_package",
            "Retrieve a low-noise LLM context package for a seed node.",
            states=memory_query_states,
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
            states=[*memory_query_states, *correction_states],
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
            states=memory_query_states,
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
            states=[*memory_query_states, *contradiction_states],
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
            states=[*memory_query_states, *correction_states, *contradiction_states],
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


def _state_value(state: AgenticStateId | str) -> str:
    return state.value if isinstance(state, AgenticStateId) else str(state)
