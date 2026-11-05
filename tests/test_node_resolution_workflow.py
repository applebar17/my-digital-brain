"""Functional batching, lookup, references, and writes for node resolution."""

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pytest

from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import Msg
from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.states.ingestion.node_candidate import (
    AnimalCandidateDTO,
    EventCandidateDTO,
    KnowledgeItemCandidateDTO,
    NodeCandidateSetDTO,
    PersonCandidateDTO,
    PlaceCandidateDTO,
)
from product.application.states.ingestion.node_resolution import (
    NodeBatchPolicyDTO,
    NodeCandidateBatchDTO,
    NodeCandidateBatchPlanner,
    NodeResolutionBatchPreparer,
    NodeResolutionWriteState,
    ReferencedNodeCandidateDTO,
)
from product.application.tools.graph_action import build_graph_action_tool
from product.graph import (
    GraphIdentityLookupService,
    GraphNodeRepository,
    GraphNodeService,
    KnowledgeItemKind,
    NodeCreate,
    NodeType,
    PersonNodeCreateDTO,
    StoredNodeDTO,
)
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class InMemoryNodeRepository(GraphNodeRepository):
    """Small typed graph boundary used by the functional resolution tests."""

    def __init__(self, nodes: Iterable[StoredNodeDTO] = ()) -> None:
        self.nodes = {node.backend_id: node for node in nodes}
        self.created = 0

    def search_nodes(
        self,
        owner_id: str,
        node_type: NodeType,
        terms: list[str],
        *,
        limit: int,
    ) -> list[StoredNodeDTO]:
        normalized = [term.casefold() for term in terms]
        matches = []
        for stored in self.nodes.values():
            if stored.backend_id == owner_id or stored.node.node_type != node_type:
                continue
            text = " ".join(
                [
                    getattr(stored.node, "display_name", "") or "",
                    getattr(stored.node, "name", "") or "",
                    getattr(stored.node, "title", "") or "",
                    *stored.node.aliases,
                ]
            ).casefold()
            if any(term in text for term in normalized):
                matches.append(stored)
        return matches[:limit]

    def get_node(
        self,
        owner_id: str,
        backend_id: str,
        node_type: NodeType,
    ) -> StoredNodeDTO:
        node = self.nodes[backend_id]
        if node.node.node_type != node_type:
            raise ValueError("Existing node type does not match the requested patch.")
        return node

    def create_node(self, owner_id: str, node: NodeCreate) -> StoredNodeDTO:
        self.created += 1
        stored = StoredNodeDTO(backend_id=f"created-{self.created}", node=node)
        self.nodes[stored.backend_id] = stored
        return stored

    def update_node(
        self,
        owner_id: str,
        backend_id: str,
        node: NodeCreate,
    ) -> StoredNodeDTO:
        stored = StoredNodeDTO(backend_id=backend_id, node=node)
        self.nodes[backend_id] = stored
        return stored


def _person(index: int, *, name: str | None = None) -> PersonCandidateDTO:
    display_name = name or f"Person {index}"
    return PersonCandidateDTO(
        node_type=NodeType.PERSON,
        description=f"Candidate {display_name}.",
        aliases=[],
        identity_gaps=[],
        display_name=display_name,
        given_name=display_name.split()[0],
        surname=None,
        known_since=None,
    )


def _place(index: int) -> PlaceCandidateDTO:
    return PlaceCandidateDTO(
        node_type=NodeType.PLACE,
        description=f"Place candidate {index}.",
        aliases=[],
        identity_gaps=[],
        name=f"Place {index}",
        address=None,
        city=None,
        region=None,
        country=None,
        place_precision=None,
        owner_hint=None,
    )


def test_batch_policy_dedicates_large_types_and_pools_small_remainders() -> None:
    candidates = NodeCandidateSetDTO(
        candidates=[
            *[_person(index) for index in range(30)],
            *[_place(index) for index in range(5)],
            KnowledgeItemCandidateDTO(
                node_type=NodeType.KNOWLEDGE_ITEM,
                description="An idea.",
                aliases=[],
                identity_gaps=[],
                knowledge_kind=KnowledgeItemKind.IDEA,
                title="Idea",
                content="Retain this idea.",
                attribution=None,
                reminder_at=None,
            ),
            EventCandidateDTO(
                node_type=NodeType.EVENT,
                description="An event.",
                aliases=[],
                identity_gaps=[],
                title="Event",
                started_at=None,
                ended_at=None,
                time_precision=None,
                organizer_hint=None,
            ),
            AnimalCandidateDTO(
                node_type=NodeType.ANIMAL,
                description="An animal.",
                aliases=[],
                identity_gaps=[],
                name="Luna",
                species="dog",
                breed=None,
                sex=None,
                owner_hint=None,
            ),
        ]
    )
    context = ReferenceContext()
    batches = NodeCandidateBatchPlanner(NodeBatchPolicyDTO()).plan(candidates, context)

    assert [len(batch.candidates) for batch in batches] == [15, 15, 5, 3]
    assert [batch.node_types for batch in batches] == [
        [NodeType.PERSON],
        [NodeType.PERSON],
        [NodeType.PLACE],
        [NodeType.KNOWLEDGE_ITEM, NodeType.EVENT, NodeType.ANIMAL],
    ]
    assert len({item.candidate_ref for batch in batches for item in batch.candidates}) == 38

    compact_batches = NodeCandidateBatchPlanner(
        NodeBatchPolicyDTO(maximum_batch_size=2, dedicated_type_minimum=2)
    ).plan(
        NodeCandidateSetDTO(candidates=[_person(40), _person(41), _place(40)]),
        ReferenceContext(),
    )
    assert [len(batch.candidates) for batch in compact_batches] == [2, 1]


def test_lookup_update_and_create_share_model_references_without_backend_ids() -> None:
    existing = StoredNodeDTO(
        backend_id="person-jacopo-backend",
        node=PersonNodeCreateDTO(
            node_type=NodeType.PERSON,
            description="A known person.",
            aliases=["Jacopo"],
            display_name="Jacopo Brutti",
            given_name="Jacopo",
            surname="Brutti",
            known_since=None,
        ),
    )
    repository = InMemoryNodeRepository([existing])
    graph_service = GraphNodeService(repository)
    reference_context = ReferenceContext()
    owner = reference_context.register_owner(
        "owner-backend",
        name="Mario",
        surname="Rossi",
    )
    candidates = NodeCandidateSetDTO(candidates=[_person(1, name="Jacopo")])
    batch = NodeCandidateBatchPlanner(NodeBatchPolicyDTO()).plan(
        candidates,
        reference_context,
    )[0]
    prepared = NodeResolutionBatchPreparer(
        owner_id="owner-backend",
        identity_lookup=GraphIdentityLookupService(repository),
        reference_context=reference_context,
    ).prepare(batch, owner)

    match = prepared.identity_evidence[0].matches[0]
    assert match.existing_ref.startswith("node_")
    assert "person-jacopo-backend" not in prepared.model_dump_json()

    tool = build_graph_action_tool(
        owner_id="owner-backend",
        service=graph_service,
        reference_context=reference_context,
        batch=batch,
    )
    update = tool.invoke(
        action={
            "operation": "update",
            "node_type": "person",
            "candidate_ref": batch.candidates[0].candidate_ref,
            "target_ref": match.existing_ref,
            "patch": {
                "node_type": "person",
                "description": None,
                "aliases_to_add": ["Jaco"],
                "display_name": None,
                "given_name": None,
                "surname": None,
                "known_since": "University",
            },
        }
    )

    assert update.node_ref == match.existing_ref
    assert repository.nodes["person-jacopo-backend"].node.aliases == ["Jacopo", "Jaco"]
    assert repository.nodes["person-jacopo-backend"].node.known_since == "University"

    new_candidate = _person(2, name="Giulia Verdi")
    new_entry = reference_context.allocate_proposed(
        object_kind=ReferenceObjectKind.CANDIDATE,
        label="Person",
        display_name="Giulia Verdi",
    )
    new_batch = NodeCandidateBatchDTO(
        batch_id="node_batch_0002",
        node_types=[NodeType.PERSON],
        candidates=[
            ReferencedNodeCandidateDTO(
                candidate_ref=new_entry.ref,
                candidate=new_candidate,
            )
        ],
    )
    create_tool = build_graph_action_tool(
        owner_id="owner-backend",
        service=graph_service,
        reference_context=reference_context,
        batch=new_batch,
    )
    created = create_tool.invoke(
        action={
            "operation": "create",
            "node_type": "person",
            "candidate_ref": new_entry.ref,
            "node": new_candidate.model_dump(exclude={"identity_gaps"}),
        }
    )

    assert created.node_ref.startswith("node_new_")
    assert reference_context.resolve(created.node_ref) == "created-1"
    with pytest.raises(ValueError, match="already created"):
        create_tool.invoke(
            action={
                "operation": "create",
                "node_type": "person",
                "candidate_ref": new_entry.ref,
                "node": new_candidate.model_dump(exclude={"identity_gaps"}),
            }
        )


def test_resolution_state_builds_a_batch_narrowed_toolbox_and_safe_prompt() -> None:
    repository = InMemoryNodeRepository()
    reference_context = ReferenceContext()
    owner = reference_context.register_owner(
        "owner-backend",
        name="Mario",
        surname="Rossi",
    )
    batch = NodeCandidateBatchPlanner(NodeBatchPolicyDTO()).plan(
        NodeCandidateSetDTO(candidates=[_person(1, name="Jacopo")]),
        reference_context,
    )[0]
    state_input = NodeResolutionBatchPreparer(
        owner_id="owner-backend",
        identity_lookup=GraphIdentityLookupService(repository),
        reference_context=reference_context,
    ).prepare(batch, owner)
    history = AgenticHistorySession([Msg(role="user", content="I met Jacopo.")])
    parent = history.start_state("conversation_entry", history.master_history)
    invocation_context = AgenticToolInvocationContext(
        history_session=history,
        parent_state_run_id=parent.state_run_id,
        parent_provider_call_id="ingest-call",
    )
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    state = NodeResolutionWriteState(
        cast(LLMInterfaceCore, object()),
        history,
        PromptService(FilePromptTemplateSource(templates_root), PromptRenderer()),
        owner_id="owner-backend",
        graph_service=GraphNodeService(repository),
        reference_context=reference_context,
    )

    configuration = state.build_invocation(state_input, invocation_context)
    assert configuration.parallel_tool_calls is True
    assert configuration.toolbox is not None
    assert list(configuration.toolbox.tools_by_name) == ["write_graph_node"]
    schema_text = str(configuration.toolbox.definitions[0].input_model.model_json_schema())
    assert "PersonNodeCreateDTO" in schema_text
    assert "PlaceNodeCreateDTO" not in schema_text
    assert "owner-backend" not in configuration.system_prompt
    assert batch.candidates[0].candidate_ref in configuration.system_prompt
