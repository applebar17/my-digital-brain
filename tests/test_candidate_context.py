from __future__ import annotations

import json

from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult
from my_digital_brain.ingestion import (
    BoundedCandidateContextHydrator,
    EntityLookupCandidate,
    EntityLookupContextPacket,
    EntityLookupRelatedContext,
    EntityLookupRequest,
    EntityLookupResult,
    IdentityLookupStatus,
    IdentityMatchKind,
    RunReferenceRegistry,
    packets_for_references,
)
from my_digital_brain.ingestion.contracts import ExtractionTask, IngestionContextPackage
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.prompt_builders import IngestionPromptBuilder


class FakeContextGraph:
    def __init__(self) -> None:
        self.nodes = {
            node.properties["id"]: node
            for node in [
                _node("person:owner", "The Owner"),
                _node("person:marco", "Marco Bianchi", aliases=["Marco"]),
                _node("org:example", "Example Corp"),
                _node("place:milan", "Milan", label="Place", city="Milan"),
                _node("person:hidden", "Hidden Person", lifecycle="archived"),
            ]
        }
        self.relationships = [
            RelationshipResult(
                type="WORKS_AT",
                from_id="person:marco",
                to_id="org:example",
                properties={"id": "rel:marco:example", "description": "colleague"},
            ),
            RelationshipResult(
                type="LIVES_IN",
                from_id="person:marco",
                to_id="place:milan",
                properties={"id": "rel:marco:milan"},
            ),
            RelationshipResult(
                type="KNOWS",
                from_id="person:marco",
                to_id="person:owner",
                properties={"id": "rel:marco:owner", "relationship_detail": "friend"},
            ),
            RelationshipResult(
                type="KNOWS",
                from_id="person:marco",
                to_id="person:hidden",
                properties={"id": "rel:hidden", "lifecycle_state": "archived"},
            ),
        ]
        self.logs = [
            _node(
                "memory:dinner",
                "Dinner memory",
                label="MemoryLog",
                log_text="Dinner with Marco Bianchi.",
                original_user_words="I had dinner with Marco Bianchi.",
                happened_at="2026-07-19",
            ),
            _node(
                "memory:hidden",
                "Hidden memory",
                label="MemoryLog",
                log_text="Private note.",
                privacy_level="local_only",
            ),
        ]

    def get_node(self, node_id: str) -> NodeSearchResult:
        return self.nodes[node_id]

    def get_node_relationships(self, node_id: str, **_kwargs: object) -> list[RelationshipResult]:
        return [
            relationship
            for relationship in self.relationships
            if relationship.from_id == node_id or relationship.to_id == node_id
        ]

    def get_memory_logs_for_target(self, node_id: str, **_kwargs: object) -> list[NodeSearchResult]:
        return self.logs if node_id == "person:marco" else []


def _node(
    node_id: str,
    title: str,
    *,
    label: str = "Person",
    aliases: list[str] | None = None,
    lifecycle: str = "active",
    privacy_level: str = "normal",
    **properties: str,
) -> NodeSearchResult:
    return NodeSearchResult(
        label=label,
        labels=[label],
        properties={
            "id": node_id,
            "display_name": title,
            "aliases": aliases or [],
            "lifecycle_state": lifecycle,
            "privacy_level": privacy_level,
            **properties,
        },
    )


def _packet() -> tuple[EntityLookupContextPacket, RunReferenceRegistry]:
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    registry.register_owner("person:owner", display_label="The Owner")
    candidate_ref = registry.register_existing(
        "person:marco",
        object_kind="node",
        label="Person",
        display_label="Marco Bianchi",
        aliases=["Marco"],
    )
    result = EntityLookupResult(
        candidate_ref="CANDIDATE_PERSON_001",
        status=IdentityLookupStatus.ONE_CANDIDATE,
        candidates=[
            EntityLookupCandidate(
                ref=candidate_ref,
                label="Person",
                display_name="Marco Bianchi",
                aliases=["Marco"],
                match_kind=IdentityMatchKind.EXACT_NAME,
                related_context=EntityLookupRelatedContext(),
            ),
        ],
    )
    return (
        EntityLookupContextPacket(
            candidate_ref="CANDIDATE_PERSON_001",
            entity_type="Person",
            proposed_display_name="Marco",
            lookup=result,
        ),
        registry,
    )


def test_hydrator_adds_bounded_relationships_places_owner_and_memory_evidence() -> None:
    packet, registry = _packet()
    hydrated = BoundedCandidateContextHydrator(
        FakeContextGraph(),
        owner_graph_node_id="person:owner",
    ).hydrate_packets([packet], registry=registry)[0]

    context = hydrated.lookup.candidates[0].related_context
    assert any("OWNER" in item for item in context.relationship_summaries)
    assert any("Example Corp" in item for item in context.relationship_summaries)
    assert context.place_hints == ["Milan (Milan)"]
    assert context.relevant_memory_summaries[0].startswith("MEMORY_000001:")
    assert "[USER_EVIDENCE]" in context.relevant_memory_summaries[0]
    assert "person:marco" not in json.dumps(hydrated.model_dump(mode="json"))
    assert "memory:dinner" not in json.dumps(hydrated.model_dump(mode="json"))
    assert registry.alias_for_internal("rel:marco:example").startswith("REL_")
    assert registry.alias_for_internal("memory:dinner").startswith("MEMORY_")


def test_hydrator_excludes_archived_and_local_only_context() -> None:
    packet, registry = _packet()
    hydrated = BoundedCandidateContextHydrator(FakeContextGraph()).hydrate_packets(
        [packet], registry=registry
    )[0]

    context = hydrated.lookup.candidates[0].related_context
    assert all("Hidden" not in item for item in context.relationship_summaries)
    assert all("Private" not in item for item in context.relevant_memory_summaries)


def test_hydrator_enforces_total_context_limit() -> None:
    packet, registry = _packet()
    hydrated = BoundedCandidateContextHydrator(
        FakeContextGraph(),
        max_total_chars=500,
    ).hydrate_packets([packet], registry=registry)

    payload = json.dumps(
        [item.model_dump(mode="json", exclude_none=True) for item in hydrated],
        ensure_ascii=False,
    )
    assert len(payload) <= 500


def test_packets_are_selected_by_candidate_or_required_existing_reference() -> None:
    first, registry = _packet()
    second = first.model_copy(
        update={
            "candidate_ref": "CANDIDATE_PERSON_002",
            "lookup": first.lookup.model_copy(
                update={"candidate_ref": "CANDIDATE_PERSON_002"},
            ),
        },
    )

    assert [item.candidate_ref for item in packets_for_references(
        [first, second], ["NODE_000001"]
    )] == ["CANDIDATE_PERSON_001", "CANDIDATE_PERSON_002"]
    assert [item.candidate_ref for item in packets_for_references(
        [first, second], ["CANDIDATE_PERSON_002"]
    )] == ["CANDIDATE_PERSON_002"]
    assert packets_for_references([first], []) == []
    assert registry.entry_for("OWNER").ref == "OWNER"


def test_extraction_prompt_receives_only_task_relevant_packets() -> None:
    first, registry = _packet()
    second = first.model_copy(
        update={
            "candidate_ref": "CANDIDATE_PERSON_002",
            "lookup": first.lookup.model_copy(
                update={"candidate_ref": "CANDIDATE_PERSON_002"},
            ),
        },
    )
    context = IngestionContextPackage(
        source_id="source-1",
        identity_lookup_packets=[first, second],
        reference_registry_snapshot=registry.snapshot(),
    )
    task = ExtractionTask(
        task_type=ExtractionTaskType.PERSON,
        target_ref="CANDIDATE_PERSON_001",
    )

    payload = IngestionPromptBuilder().extraction_input(
        source=type("Source", (), {"metadata": {}})(),
        task=task,
        context=context,
    )

    packets = payload["compact_graph_context"]["identity_lookup_packets"]
    assert [item["candidate_ref"] for item in packets] == ["CANDIDATE_PERSON_001"]
