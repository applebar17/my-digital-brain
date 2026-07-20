from __future__ import annotations

from types import SimpleNamespace

import pytest

from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.ingestion import (
    DeterministicIdentityLookupService,
    IdentityLookupError,
    IngestionService,
    RunReferenceRegistry,
    WholeSourceGraphContextPackBuilder,
    request_from_planned_entity,
)
from my_digital_brain.ingestion.contracts import (
    EntityIngestionActionDraft,
    EntityIngestionPlanDraft,
    EntityLookupRequest,
    IdentityLookupStatus,
    IdentityMatchKind,
    PlannedEntityRefDraft,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import SourceChannel, SourceType
from my_digital_brain.ingestion.ontology import LLMEntityType


class FakeIdentityGraph:
    def __init__(self, nodes: list[NodeSearchResult]) -> None:
        self.nodes = nodes
        self.calls: list[dict[str, object]] = []

    def search_nodes(self, **kwargs: object) -> list[NodeSearchResult]:
        self.calls.append(kwargs)
        return self.nodes


def _node(
    node_id: str,
    name: str,
    *,
    aliases: list[str] | None = None,
    lifecycle: str = "active",
) -> NodeSearchResult:
    return NodeSearchResult(
        label="Person",
        labels=["Person"],
        properties={
            "id": node_id,
            "display_name": name,
            "aliases": aliases or [],
            "lifecycle_state": lifecycle,
        },
    )


def _request(**updates: object) -> EntityLookupRequest:
    values: dict[str, object] = {
        "candidate_ref": "CANDIDATE_PERSON_001",
        "entity_type": "Person",
        "display_name": "Marco",
        "max_candidates": 5,
    }
    values.update(updates)
    return EntityLookupRequest.model_validate(values)


def test_request_is_derived_from_planned_entity_fields() -> None:
    planned = PlannedEntityRefDraft(
        local_ref="CANDIDATE_PERSON_001",
        mention_text="Marco Bianchi",
        suggested_entity_type=LLMEntityType.PERSON,
        aliases=["Bianchino"],
    )

    request = request_from_planned_entity(planned)

    assert request.candidate_ref == "CANDIDATE_PERSON_001"
    assert request.entity_type == "Person"
    assert request.display_name == "Marco Bianchi"
    assert request.aliases == ["Bianchino"]


def test_lookup_returns_multiple_deterministic_candidates_and_registers_aliases() -> None:
    graph = FakeIdentityGraph([
        _node("marco-bianchi", "Marco Bianchi"),
        _node("marco-verdi", "Marco Verdi"),
        _node("luca", "Luca Rossi"),
    ])
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    service = DeterministicIdentityLookupService(graph)

    result = service.lookup(_request(), registry=registry)

    assert result.status == IdentityLookupStatus.MULTIPLE_CANDIDATES
    assert [candidate.display_name for candidate in result.candidates] == [
        "Marco Bianchi",
        "Marco Verdi",
    ]
    assert [candidate.ref for candidate in result.candidates] == [
        "NODE_000001",
        "NODE_000002",
    ]
    assert all("marco" in str(call["query"]).casefold() for call in graph.calls)
    assert registry.resolve("NODE_000001") == "marco-bianchi"


def test_lookup_matches_aliases_and_name_tokens() -> None:
    graph = FakeIdentityGraph([
        _node("matteo", "Matteo Mercoldi", aliases=["Merc"]),
        _node("marco", "Marco Bianchi"),
    ])
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    service = DeterministicIdentityLookupService(graph)

    alias_result = service.lookup(
        _request(display_name="Merc", aliases=[]),
        registry=registry,
    )
    token_result = service.lookup(_request(display_name="Marco"), registry=registry)

    assert alias_result.status == IdentityLookupStatus.ONE_CANDIDATE
    assert alias_result.candidates[0].match_kind == IdentityMatchKind.EXACT_ALIAS
    assert token_result.candidates[0].match_kind == IdentityMatchKind.NAME_TOKEN


def test_owner_and_archived_people_are_excluded() -> None:
    graph = FakeIdentityGraph([
        _node("person:owner", "Marco Owner"),
        _node("archived", "Marco Archived", lifecycle="archived"),
        _node("active", "Marco Active"),
    ])
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    service = DeterministicIdentityLookupService(
        graph,
        owner_graph_node_id="person:owner",
    )

    result = service.lookup(_request(), registry=registry)

    assert result.status == IdentityLookupStatus.ONE_CANDIDATE
    assert result.candidates[0].display_name == "Marco Active"
    assert registry.resolve("NODE_000001") == "active"


def test_fuzzy_candidates_are_hints_only_when_explicitly_supported() -> None:
    class FuzzyGraph(FakeIdentityGraph):
        def search_identity_fuzzy(
            self,
            request: EntityLookupRequest,
            *,
            limit: int,
        ) -> list[NodeSearchResult]:
            return [_node("fuzzy", "Marko Bianchi")]

    graph = FuzzyGraph([])
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    result = DeterministicIdentityLookupService(graph).lookup(
        _request(display_name="Marqo"),
        registry=registry,
    )

    assert result.status == IdentityLookupStatus.FUZZY_CANDIDATES_ONLY
    assert result.candidates[0].match_kind == IdentityMatchKind.FUZZY_HINT


def test_lookup_failure_does_not_return_no_candidates() -> None:
    class FailingGraph:
        def search_nodes(self, **_kwargs: object) -> list[NodeSearchResult]:
            raise RuntimeError("database unavailable")

    with pytest.raises(IdentityLookupError):
        DeterministicIdentityLookupService(FailingGraph()).lookup(
            _request(),
            registry=RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1"),
        )


def test_lookup_plan_produces_extraction_packets_without_internal_ids() -> None:
    graph = FakeIdentityGraph([_node("person-uuid-marco", "Marco Bianchi")])
    planned = PlannedEntityRefDraft(
        local_ref="CANDIDATE_PERSON_001",
        mention_text="Marco",
        suggested_entity_type=LLMEntityType.PERSON,
    )
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    packets = DeterministicIdentityLookupService(graph).lookup_plan(
        SimpleNamespace(actions=[SimpleNamespace(entities=[planned])]),
        registry=registry,
    )

    payload = packets[0].model_dump(mode="json")
    assert packets[0].lookup.candidates[0].ref == "NODE_000001"
    assert "person-uuid-marco" not in str(payload)
    assert registry.backend_alias_map()["NODE_000001"] == "person-uuid-marco"


def test_runtime_attaches_lookup_packets_after_planning_before_extraction() -> None:
    graph = FakeIdentityGraph([_node("person-uuid-marco", "Marco Bianchi")])
    source = SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Marco.",
    )
    graph_pack = WholeSourceGraphContextPackBuilder(graph_service=graph).build(source)
    plan = EntityIngestionPlanDraft(
        actions=[EntityIngestionActionDraft(
            goal="Prepare Marco",
            entities=[PlannedEntityRefDraft(
                local_ref="CANDIDATE_PERSON_001",
                mention_text="Marco",
                suggested_entity_type=LLMEntityType.PERSON,
            )],
        )],
    )
    runtime = IngestionService(
        reasoning_service=object(),
        planning_service=object(),
        graph_context_builder=object(),
        identity_lookup_service=DeterministicIdentityLookupService(graph),
    )

    runtime._attach_identity_lookup_packets(source, graph_pack, plan)

    assert graph_pack.identity_lookup_packets[0].lookup.status == (
        IdentityLookupStatus.ONE_CANDIDATE
    )
    assert graph_pack.identity_lookup_packets[0].lookup.candidates[0].ref == "NODE_000001"
    assert graph_pack.alias_map["NODE_000001"] == "person-uuid-marco"
