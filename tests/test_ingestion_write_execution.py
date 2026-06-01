from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult
from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateOutput,
    CandidateRelationship,
    ExtractionPlan,
    ExtractionTask,
    IngestionContextPackage,
    Mention,
    MentionScan,
    ResolutionDecision,
    ResolutionResult,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import (
    ExtractionExecutionMode,
    ExtractionTaskType,
    IngestionStatus,
    MentionKind,
    ResolutionDecisionType,
    SourceChannel,
    SourceType,
)
from my_digital_brain.ingestion.executor import GraphWritePlanExecutor
from my_digital_brain.ingestion.resolution import ConservativeResolutionService
from my_digital_brain.ingestion.service import IngestionService
from my_digital_brain.ingestion.session_store import InMemoryIngestionProcessStore
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder


def test_conservative_resolution_matches_one_exact_existing_node() -> None:
    existing_id = new_uuid()
    graph = FakeGraphService(
        nodes=[
            _node("Person", existing_id, display_name="Marco Rossi", aliases=["Marco"]),
        ],
    )
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco Rossi",
                source_refs=["source-1"],
            ),
        ],
    )

    result = ConservativeResolutionService(graph).resolve(candidate_graph)

    assert result.clarification is None
    assert result.decisions[0].decision_type == ResolutionDecisionType.MATCH_EXISTING
    assert result.decisions[0].target_entity_id == existing_id


def test_conservative_resolution_returns_clarification_for_ambiguous_matches() -> None:
    graph = FakeGraphService(
        nodes=[
            _node("Person", new_uuid(), display_name="Marco Rossi"),
            _node("Person", new_uuid(), display_name="Marco Rossi"),
        ],
    )
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco Rossi",
                source_refs=["source-1"],
            ),
        ],
    )

    result = ConservativeResolutionService(graph).resolve(candidate_graph)

    assert result.clarification is not None
    assert result.clarification.target_refs == ["CANDIDATE_PERSON_001"]
    assert result.decisions[0].decision_type == ResolutionDecisionType.ASK_CLARIFICATION


def test_write_plan_builder_maps_candidate_refs_and_is_deterministic() -> None:
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco",
                source_refs=["source-1"],
            ),
            CandidateEntity(
                local_ref="CANDIDATE_PLACE_001",
                entity_type="Place",
                display_name="Milan",
                source_refs=["source-1"],
            ),
            CandidateRelationship(
                local_ref="CANDIDATE_REL_001",
                relationship_type="HAPPENED_AT",
                from_ref="CANDIDATE_PERSON_001",
                to_ref="CANDIDATE_PLACE_001",
                source_refs=["source-1"],
            ),
        ],
    )

    builder = GraphWritePlanBuilder()
    plan = builder.build(candidate_graph, _create_resolution(candidate_graph))
    same_plan = builder.build(candidate_graph, _create_resolution(candidate_graph))

    assert len(plan.nodes_to_create) == 2
    assert plan.relationships_to_create[0].from_ref == "CANDIDATE_PERSON_001"
    assert plan.nodes_to_create[0].properties["id"] == same_plan.nodes_to_create[0].properties["id"]
    assert plan.idempotency_keys == same_plan.idempotency_keys


def test_write_plan_builder_uses_existing_resolution_for_relationship_endpoints() -> None:
    existing_id = new_uuid()
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco",
                source_refs=["source-1"],
            ),
            CandidateEntity(
                local_ref="CANDIDATE_PLACE_001",
                entity_type="Place",
                display_name="Milan",
                source_refs=["source-1"],
            ),
            CandidateRelationship(
                local_ref="CANDIDATE_REL_001",
                relationship_type="HAPPENED_AT",
                from_ref="CANDIDATE_PERSON_001",
                to_ref="CANDIDATE_PLACE_001",
                source_refs=["source-1"],
            ),
        ],
    )
    resolution = ResolutionResult(
        decisions=[
            ResolutionDecision(
                candidate_ref="CANDIDATE_PERSON_001",
                decision_type=ResolutionDecisionType.MATCH_EXISTING,
                target_entity_id=existing_id,
            ),
            ResolutionDecision(
                candidate_ref="CANDIDATE_PLACE_001",
                decision_type=ResolutionDecisionType.CREATE,
            ),
        ],
    )

    plan = GraphWritePlanBuilder().build(candidate_graph, resolution)
    graph = FakeGraphService(nodes=[_node("Person", existing_id)])
    result = GraphWritePlanExecutor(graph).execute(plan)

    assert len(plan.nodes_to_create) == 1
    assert plan.metadata["local_ref_resolution"] == {"CANDIDATE_PERSON_001": existing_id}
    assert result.status == IngestionStatus.WRITTEN
    assert result.metadata["relationships"] == 1


def test_executor_calls_graph_service_and_preserves_provenance() -> None:
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco",
                source_refs=["source-1"],
            ),
        ],
    )
    plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))
    graph = FakeGraphService()

    result = GraphWritePlanExecutor(graph).execute(plan)

    assert result.status == IngestionStatus.WRITTEN
    assert graph.upserted_nodes[0].properties["source_ids"] == ["source-1"]
    assert result.write_plan is not None
    assert result.write_plan.status == "executed"


def test_executor_rejects_repeated_application_of_executed_plan() -> None:
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco",
                source_refs=["source-1"],
            ),
        ],
    )
    plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))
    executor = GraphWritePlanExecutor(FakeGraphService())

    assert executor.execute(plan).status == IngestionStatus.WRITTEN
    second_result = executor.execute(plan)

    assert second_result.status == IngestionStatus.FAILED
    assert "already been executed" in second_result.validation_errors[0].message


def test_ingestion_service_can_execute_fake_write_path() -> None:
    graph = FakeGraphService()
    service = IngestionService(
        scanner=StaticScanner(),
        context_retriever=StaticContextRetriever(),
        planner=StaticPlanner(_plan()),
        extractors=[
            StaticExtractor(
                [
                    CandidateEntity(
                        local_ref="CANDIDATE_PERSON_001",
                        entity_type="Person",
                        display_name="Marco",
                        source_refs=["source-1"],
                    ),
                ],
            ),
        ],
        resolution_service=ConservativeResolutionService(graph),
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph),
        execute_write_plan=True,
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.WRITTEN
    assert result.candidate_graph is not None
    assert graph.upserted_nodes[0].label == "Person"


def test_ingestion_service_pauses_on_resolution_clarification() -> None:
    graph = FakeGraphService(
        nodes=[
            _node("Person", new_uuid(), display_name="Marco Rossi"),
            _node("Person", new_uuid(), display_name="Marco Rossi"),
        ],
    )
    service = IngestionService(
        scanner=StaticScanner(),
        context_retriever=StaticContextRetriever(),
        planner=StaticPlanner(_plan()),
        extractors=[
            StaticExtractor(
                [
                    CandidateEntity(
                        local_ref="CANDIDATE_PERSON_001",
                        entity_type="Person",
                        display_name="Marco Rossi",
                        source_refs=["source-1"],
                    ),
                ],
            ),
        ],
        resolution_service=ConservativeResolutionService(graph),
        write_plan_builder=GraphWritePlanBuilder(),
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.NEEDS_CLARIFICATION
    assert result.clarification is not None
    assert result.clarification.target_refs == ["CANDIDATE_PERSON_001"]


def test_process_store_records_source_snapshots_and_expires_pending_sessions() -> None:
    store = InMemoryIngestionProcessStore()
    graph = FakeGraphService(
        nodes=[
            _node("Person", new_uuid(), display_name="Marco Rossi"),
            _node("Person", new_uuid(), display_name="Marco Rossi"),
        ],
    )
    service = IngestionService(
        scanner=StaticScanner(),
        context_retriever=StaticContextRetriever(),
        planner=StaticPlanner(_plan()),
        extractors=[
            StaticExtractor(
                [
                    CandidateEntity(
                        local_ref="CANDIDATE_PERSON_001",
                        entity_type="Person",
                        display_name="Marco Rossi",
                        source_refs=["source-1"],
                    ),
                ],
            ),
        ],
        resolution_service=ConservativeResolutionService(graph),
        write_plan_builder=GraphWritePlanBuilder(),
        process_store=store,
    )

    result = service.process_source(_source())
    snapshot = store.get_session(result.ingestion_id)
    assert snapshot is not None
    assert store.sources["source-1"].raw_text == "I met Marco in Milan."
    assert snapshot.pending_question == "Which existing memory should this refer to?"

    expired_snapshot = snapshot.model_copy(
        update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
    )
    store.sessions[snapshot.session_id] = expired_snapshot
    expired_ids = store.expire_pending()

    assert expired_ids == [snapshot.session_id]
    assert store.sessions[snapshot.session_id].metadata["expired"] is True


class FakeGraphService:
    def __init__(self, nodes: list[NodeSearchResult] | None = None) -> None:
        self.nodes = {node.properties["id"]: node for node in nodes or []}
        self.upserted_nodes: list[NodeSearchResult] = []
        self.relationships: list[RelationshipResult] = []

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        limit: int = 25,
        **_: Any,
    ) -> list[NodeSearchResult]:
        normalized_query = str(query or "").lower()
        matches = []
        for node in self.nodes.values():
            if label and node.label != label:
                continue
            values = [str(value).lower() for value in node.properties.values()]
            if not query or any(normalized_query in value for value in values):
                matches.append(node)
        return matches[:limit]

    def upsert_node(self, label: str, properties: dict[str, Any]) -> NodeSearchResult:
        node = _node(label, properties["id"], **properties)
        self.nodes[node.properties["id"]] = node
        self.upserted_nodes.append(node)
        return node

    def patch_node(self, node_id: str, properties: dict[str, Any]) -> NodeSearchResult:
        node = self.nodes[node_id]
        patched = dict(node.properties)
        patched.update(properties)
        self.nodes[node_id] = _node(node.label, node_id, **patched)
        return self.nodes[node_id]

    def get_node(self, node_id: str) -> NodeSearchResult:
        return self.nodes[node_id]

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> RelationshipResult:
        relationship = RelationshipResult(
            type=relationship_type,
            from_id=from_id,
            to_id=to_id,
            properties=properties,
        )
        self.relationships.append(relationship)
        return relationship


class StaticScanner:
    def scan(self, source: SourceRecordRef) -> MentionScan:
        return MentionScan(
            source_id=source.source_id,
            mentions=[Mention(kind=MentionKind.PERSON, text="Marco")],
        )


class StaticContextRetriever:
    def retrieve(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
    ) -> IngestionContextPackage:
        return IngestionContextPackage(source_id=source.source_id)


class StaticPlanner:
    def __init__(self, plan: ExtractionPlan) -> None:
        self.plan_value = plan

    def plan(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        return self.plan_value


class StaticExtractor:
    def __init__(self, candidates: Sequence[CandidateOutput]) -> None:
        self.candidates = candidates

    def supports(self, task: ExtractionTask) -> bool:
        return task.task_type == ExtractionTaskType.PERSON

    def extract(
        self,
        source: SourceRecordRef,
        task: ExtractionTask,
        context: IngestionContextPackage,
    ) -> Sequence[CandidateOutput]:
        return self.candidates


def _candidate_graph(candidates: Sequence[CandidateOutput]):
    return CandidateMemoryGraphAssembler().assemble(_source(), _plan(), candidates)


def _create_resolution(candidate_graph) -> ResolutionResult:
    return ResolutionResult(
        decisions=[
            ResolutionDecision(
                candidate_ref=candidate.local_ref,
                decision_type=ResolutionDecisionType.CREATE,
            )
            for candidate in candidate_graph.candidate_entities
        ],
    )


def _node(label: str, node_id: str, **properties: Any) -> NodeSearchResult:
    normalized = {"id": node_id, **properties}
    return NodeSearchResult(label=label, labels=[label], properties=normalized)


def _source() -> SourceRecordRef:
    return SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Marco in Milan.",
    )


def _plan() -> ExtractionPlan:
    return ExtractionPlan(
        source_id="source-1",
        execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        tasks=[
            ExtractionTask(
                task_type=ExtractionTaskType.PERSON,
                evidence_text="Marco",
                source_refs=["source-1"],
            ),
        ],
    )
