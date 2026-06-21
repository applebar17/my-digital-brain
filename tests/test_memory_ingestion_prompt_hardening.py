from __future__ import annotations

import re

from my_digital_brain.agentic import (
    AliasReasoningHint,
    EdgeMemoryPlan,
    EdgeReasoningHighlights,
    IrrelevantDetailHint,
    MemoryIngestionReasoning,
    MemoryLogMemoryPlan,
    MemoryPlanAction,
    MemoryPlanActionType,
    MemoryPlanPacket,
    MemoryPlanStep,
    MemoryPlanningPhase,
    NodeMemoryPlan,
    NodePlanPacket,
    NodeReasoningHighlights,
    PlanExecutionMode,
    PlannedRefPacket,
    ReasoningHighlights,
)
from my_digital_brain.prompts import ACTIVE_PROMPT_TEMPLATES, MEMORY_PROMPT_TEMPLATES, PromptRegistry


UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

PROMPT_VARIABLES = {
    "graph_context": "Hydrated graph context:\n- node_0001 Person: User\n- node_0002 Place: Beach",
    "aliases": "Known aliases:\n- Merc -> Matteo Mercoldi\n- Bri -> possible person alias",
    "reasoning_inventory_packet": "Reasoning inventory:\nNodes: people, places, event. Logs: barbeque, beach, card game.",
    "ref_context_packet": "Current refs:\n- node_0001 Person: User\n- node_0002 Place: Beach",
    "duplicate_candidate_packets": "Duplicate candidates:\n- Merc may match node_0007 Matteo Mercoldi",
    "node_plan_packet": "Node plan packet:\n- node_0001 User\n- node_new_0001 Lorenzo\n- node_new_0002 Merc",
    "irrelevant_details_packet": "Irrelevant details to ignore:\n- generic co-presence without relationship evidence",
    "memory_plan_packet": "Memory plan packet:\n- memory_new_0001 barbeque\n- memory_new_0002 beach outing",
    "relationship_candidate_packets": "Relationship candidates:\n- Lorenzo brother of user\n- weak beach co-presence only",
    "current_action": "Create memory_new_0001 for the barbeque episode.",
    "action_packet": "Action packet:\n- target_refs: memory_new_0001, node_0001, node_new_0001",
    "validation_error_examples": "Recoverable error example: invalid relationship type -> retry with allowed type.",
}


def test_active_prompt_constants_match_file_backed_registry() -> None:
    registry = PromptRegistry()

    for prompt_id, template in ACTIVE_PROMPT_TEMPLATES.items():
        assert registry.load(prompt_id).template == template


def test_active_prompt_family_is_lean_and_clean() -> None:
    registry = PromptRegistry()
    noise_phrases = (
        "backend ids",
        "backend id",
        "raw metadata",
        "prompt traces",
        "vector ids",
        "my digital brain",
    )

    for prompt_id, template in ACTIVE_PROMPT_TEMPLATES.items():
        rendered = registry.render(prompt_id, variables=PROMPT_VARIABLES)

        assert "# Role" in rendered
        assert "# Task" in rendered
        assert "# Context" in rendered
        assert len(template) < 1800
        assert not UUID_RE.search(rendered)
        lowered = rendered.lower()
        for phrase in noise_phrases:
            assert phrase not in lowered, f"{prompt_id} contains prompt noise: {phrase}"


def test_active_prompt_behavior_boundaries_are_present() -> None:
    registry = PromptRegistry()

    conversation = registry.load("conversation_entry").template
    assert "query_memory" in conversation
    assert "ingest_memory" in conversation
    assert "update_memory_graph" not in conversation
    assert "start_memory_ingestion" not in conversation

    ingestion = registry.render("memory_ingestion", variables=PROMPT_VARIABLES)
    assert "Stay high-level" in ingestion
    assert "do not create refs" in ingestion
    assert "Split dense episodes" in ingestion

    node = registry.render("memory_node_planning", variables=PROMPT_VARIABLES)
    memory = registry.render("memory_log_planning", variables=PROMPT_VARIABLES)
    edge = registry.render("memory_edge_planning", variables=PROMPT_VARIABLES)
    creation = registry.render("memory_creation", variables=PROMPT_VARIABLES)
    update = registry.load("graph_update").template

    assert "Node: a self-sustaining entity" in node
    assert "Resolve aliases and duplicate candidates" in node
    assert "node_plan_packet" not in node

    assert "Node plan packet" in memory
    assert "one or two giant logs" in memory
    assert "weak co-presence as log involvement" in memory

    assert "Memory plan packet" in edge
    assert "Edge endpoints must be known refs" in edge
    assert "never loose names" in edge
    assert "strong signals" in edge

    assert "Current action" in creation
    assert "Tool error" in creation
    assert "Ask clarification only when blocked" in creation
    assert "compact ref-based result" in creation

    assert "Tool error" in update
    assert "Ask clarification only when target or intent remains blocked" in update


def test_dense_republic_day_uat_shape_uses_many_logs_and_ref_edges() -> None:
    reasoning = MemoryIngestionReasoning(
        highlights=ReasoningHighlights(
            nodes=NodeReasoningHighlights(
                persons="The source identifies the user, Lorenzo, Merc, Bri, Fabione, and family/friend participants.",
                places="The important places are the barbeque location, the beach, Moon, and the evening location.",
                events="Republic Day barbeque, beach outing, card game, and later evening are separate moments.",
            ),
            logs=[
                "Republic Day barbeque with family and friends.",
                "Beach outing with Merc, Bri, Fabione, and others.",
                "Card game episode later in the day.",
                "Quiet evening and atmosphere context at Moon.",
            ],
            edges=EdgeReasoningHighlights(
                family="Lorenzo is the user's brother.",
                relationships="Only explicit strong relationship signals should become durable edges.",
                perception_or_affect="Atmosphere at Moon may require a perception/context record.",
            ),
        ),
        possible_aliases=[
            AliasReasoningHint(main_mention="Matteo Mercoldi", aliases=["Merc"]),
            AliasReasoningHint(main_mention="Bri", aliases=["Bri", "Br?"]),
            AliasReasoningHint(main_mention="Fabione", aliases=["Fabione"]),
        ],
        irrelevant_details=[
            IrrelevantDetailHint(
                detail="People being at the beach together does not prove durable friendship edges.",
                reason="Co-presence is weak relationship evidence.",
                category="weak_edge",
            )
        ],
        planning_guidance="Plan nodes first, then several compact MemoryLogs/context records, then durable edges only for strong signals.",
    )
    node_plan = NodeMemoryPlan(
        summary="Resolve people and places for the dense source.",
        steps=[
            MemoryPlanStep(
                step_id="node_step_0001",
                phase=MemoryPlanningPhase.NODES,
                execution_mode=PlanExecutionMode.PARALLEL,
                actions=[
                    MemoryPlanAction(
                        action_id="node_action_0001",
                        action_type=MemoryPlanActionType.CREATE_NODE,
                        target_refs=["node_new_0001"],
                        payload={"label": "Person", "name": "Lorenzo"},
                    ),
                    MemoryPlanAction(
                        action_id="node_action_0002",
                        action_type=MemoryPlanActionType.CREATE_NODE,
                        target_refs=["node_new_0002"],
                        payload={"label": "Person", "name": "Matteo Mercoldi", "aliases": ["Merc"]},
                    ),
                    MemoryPlanAction(
                        action_id="node_action_0003",
                        action_type=MemoryPlanActionType.CREATE_NODE,
                        target_refs=["node_new_0003"],
                        payload={"label": "Person", "name": "Bri", "aliases": ["Br?"]},
                    ),
                    MemoryPlanAction(
                        action_id="node_action_0004",
                        action_type=MemoryPlanActionType.CREATE_NODE,
                        target_refs=["node_new_0004"],
                        payload={"label": "Person", "name": "Fabione"},
                    ),
                ],
            )
        ],
        node_plan_packet=NodePlanPacket(
            planned_refs=[
                PlannedRefPacket(ref="node_new_0001", object_kind="node", label="Person", name="Lorenzo"),
                PlannedRefPacket(ref="node_new_0002", object_kind="node", label="Person", name="Matteo Mercoldi", aliases=["Merc"]),
                PlannedRefPacket(ref="node_new_0003", object_kind="node", label="Person", name="Bri", aliases=["Br?"]),
                PlannedRefPacket(ref="node_new_0004", object_kind="node", label="Person", name="Fabione"),
            ],
            summary="Aliases captured before creation to avoid duplicates.",
        ),
    )
    memory_plan = MemoryLogMemoryPlan(
        summary="Split the dense source into compact logs and context records.",
        steps=[
            MemoryPlanStep(
                step_id="memory_step_0001",
                phase=MemoryPlanningPhase.MEMORY_LOGS,
                execution_mode=PlanExecutionMode.PARALLEL,
                actions=[
                    MemoryPlanAction(action_id="memory_action_0001", action_type="create_memory_log", target_refs=["memory_new_0001", "node_new_0001"]),
                    MemoryPlanAction(action_id="memory_action_0002", action_type="create_memory_log", target_refs=["memory_new_0002", "node_new_0002", "node_new_0003", "node_new_0004"]),
                    MemoryPlanAction(action_id="memory_action_0003", action_type="create_memory_log", target_refs=["memory_new_0003"]),
                    MemoryPlanAction(action_id="memory_action_0004", action_type="create_memory_log", target_refs=["memory_new_0004"]),
                    MemoryPlanAction(action_id="memory_action_0005", action_type="create_memory_log", target_refs=["context_new_0001"], payload={"label": "Perception"}),
                ],
            )
        ],
        memory_plan_packet=MemoryPlanPacket(
            planned_refs=[
                PlannedRefPacket(ref="memory_new_0001", object_kind="memory", label="MemoryLog", summary="Republic Day barbeque."),
                PlannedRefPacket(ref="memory_new_0002", object_kind="memory", label="MemoryLog", summary="Beach outing."),
                PlannedRefPacket(ref="memory_new_0003", object_kind="memory", label="MemoryLog", summary="Card game."),
                PlannedRefPacket(ref="memory_new_0004", object_kind="memory", label="MemoryLog", summary="Quiet evening."),
                PlannedRefPacket(ref="context_new_0001", object_kind="context", label="Perception", summary="Atmosphere at Moon was not great."),
            ],
            host_refs=["node_0001"],
            involved_refs=["node_new_0001", "node_new_0002", "node_new_0003", "node_new_0004"],
            context_refs=["context_new_0001"],
            weak_edge_notes=["Beach co-presence remains involvement only."],
            summary="Dense source split into several compact records.",
        ),
    )
    edge_plan = EdgeMemoryPlan(
        summary="Create only strong durable edges.",
        steps=[
            MemoryPlanStep(
                step_id="edge_step_0001",
                phase=MemoryPlanningPhase.EDGES,
                actions=[
                    MemoryPlanAction(
                        action_id="edge_action_0001",
                        action_type="create_relationship",
                        payload={"from_ref": "node_0001", "to_ref": "node_new_0001", "relationship_type": "SIBLING"},
                    ),
                    MemoryPlanAction(
                        action_id="edge_action_0002",
                        action_type="create_relationship",
                        payload={"from_ref": "context_new_0001", "to_ref": "node_0002", "relationship_type": "ABOUT"},
                    ),
                ],
            )
        ],
        diagnostics=[{"summary": "Weak beach co-presence intentionally stayed in MemoryLog involvement."}],
    )

    assert len(reasoning.highlights.logs) >= 4
    alias_text = str(reasoning.model_dump(mode="json"))
    assert "Merc" in alias_text
    assert "Bri" in alias_text
    assert "Fabione" in alias_text
    assert len(memory_plan.memory_plan_packet.planned_refs) >= 5
    assert len([
        action
        for step in memory_plan.steps
        for action in step.actions
        if action.action_type == MemoryPlanActionType.CREATE_MEMORY_LOG.value
    ]) >= 4
    edge_payload = str(edge_plan.model_dump(mode="json"))
    assert "SIBLING" in edge_payload
    assert "node_0001" in edge_payload
    assert "node_new_0001" in edge_payload
    assert "Beach co-presence remains involvement only." in memory_plan.memory_plan_packet.weak_edge_notes
    assert "backend_id" not in str(node_plan.node_plan_packet.model_dump(mode="json"))
    assert not UUID_RE.search(str(memory_plan.memory_plan_packet.model_dump(mode="json")))
