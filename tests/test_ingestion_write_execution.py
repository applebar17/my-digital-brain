from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from my_digital_brain.agentic import (
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticStateRunner,
)
from my_digital_brain.ai.schemas import (
    ProviderCallMetadata,
    StructuredGenerationRequest,
    StructuredGenerationResult,
)
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult, SocialCircleNode
from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateOutput,
    CandidateRelationship,
    ExtractionPlan,
    ExtractionTask,
    GraphContextPack,
    GraphWritePlan,
    IngestionContextPackage,
    MemoryLog,
    MemoryLogLink,
    ResolutionDecision,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
    SourceRecordRef,
)
from my_digital_brain.ingestion.extractors import EntityExtractor, RelationshipExtractor
from my_digital_brain.ingestion.enums import (
    ExtractionExecutionMode,
    ExtractionTaskType,
    IngestionStatus,
    ResolutionDecisionType,
    SourceChannel,
    SourceType,
)
from my_digital_brain.ingestion.executor import GraphWritePlanExecutor
from my_digital_brain.ingestion.resolution_proposals import (
    ResolutionProposalCompiler,
    ResolutionProposalValidator,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.service import IngestionService
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder
from tests.support_resolution import FixedResolutionAgent


def test_structured_resolution_agent_controls_attachment_without_semantic_fallback() -> None:
    existing_id = new_uuid()
    graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco Rossi",
                source_refs=["source-1"],
            ),
        ],
    )
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    registry.register_owner("person:owner")
    existing_ref = registry.register_existing(
        existing_id,
        object_kind="node",
        label="Person",
        display_label="Marco Rossi",
    )
    agent = FixedResolutionAgent(node_action="update", target_ref=existing_ref)
    context = IngestionContextPackage(
        source_id="source-1",
        reference_registry_snapshot=registry.snapshot(),
    )

    resolved, result = agent.resolve_nodes(
        source_text="I met Marco Rossi.",
        context=context,
        candidate_graph=graph,
    )

    assert resolved.entries[0].status == "matched_existing"
    assert resolved.entries[0].graph_alias == existing_ref


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


def test_write_plan_builder_preserves_social_relationship_kind_and_detail() -> None:
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Riccardo",
                source_refs=["source-1"],
            ),
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_002",
                entity_type="Person",
                display_name="Alessia",
                source_refs=["source-1"],
            ),
            CandidateRelationship(
                local_ref="CANDIDATE_REL_001",
                relationship_type="RELATIONSHIP_WITH",
                from_ref="CANDIDATE_PERSON_001",
                to_ref="CANDIDATE_PERSON_002",
                relationship_kind="partner",
                relationship_detail="girlfriend",
                source_refs=["source-1"],
            ),
        ],
    )

    plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))
    relationship = plan.relationships_to_create[0]

    assert relationship.relationship_type == "RELATIONSHIP_WITH"
    assert relationship.properties["relationship_kind"] == "partner"
    assert relationship.properties["relationship_detail"] == "girlfriend"


def test_write_plan_builder_does_not_write_aliases_to_social_circle_nodes() -> None:
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_SOCIAL_CIRCLE_001",
                entity_type="SocialCircle",
                display_name="il suo gruppo",
                aliases=["il suo gruppo"],
                typed_properties={
                    "aliases": ["gruppo di amici"],
                    "circle_type": "friendship",
                    "unmodeled_note": "kept for debug metadata",
                },
                source_refs=["source-1"],
            ),
        ],
    )

    plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))
    node = plan.nodes_to_create[0]

    assert node.label == "SocialCircle"
    assert "aliases" not in node.properties
    assert node.properties["name"] == "il suo gruppo"
    assert node.properties["circle_type"] == "friendship"
    assert node.properties["metadata"]["unsupported_entity_properties"] == {
        "aliases": ["gruppo di amici", "il suo gruppo"],
        "unmodeled_note": "kept for debug metadata",
    }
    SocialCircleNode.model_validate(node.properties)


def test_write_plan_builder_keeps_aliases_for_alias_bearing_node_labels() -> None:
    candidate_graph = _candidate_graph(
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco Rossi",
                aliases=["Marco"],
                source_refs=["source-1"],
            ),
        ],
    )

    plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))

    assert plan.nodes_to_create[0].properties["aliases"] == ["Marco"]


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


def test_write_plan_builder_and_executor_create_memory_logs_for_existing_host() -> None:
    host_id = new_uuid()
    candidate_graph = _candidate_graph(
        [],
        memory_logs=[
            MemoryLog(
                local_ref="MEMORY_LOG_001",
                log_text="Marco changed job yesterday.",
                log_kind="update",
                primary_host_target_id=host_id,
                primary_host_target_label="Person",
                host_target_ids=[host_id],
                links=[
                    MemoryLogLink(
                        target_id=host_id,
                        target_label="Person",
                        relationship_type="HAS_MEMORY_LOG",
                        primary=True,
                        role="primary_host",
                    ),
                ],
                source_refs=["source-1"],
                media_refs=["media-ref-1"],
            ),
        ],
    )

    plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))
    same_plan = GraphWritePlanBuilder().build(candidate_graph, _create_resolution(candidate_graph))
    graph = FakeGraphService(nodes=[_node("Person", host_id, display_name="Marco")])
    result = GraphWritePlanExecutor(graph).execute(plan)

    assert len(plan.memory_logs_to_create) == 1
    assert plan.memory_logs_to_create[0].label == "MemoryLog"
    assert plan.memory_logs_to_create[0].properties["log_text"] == (
        "Marco changed job yesterday."
    )
    assert plan.memory_logs_to_create[0].properties["media_refs"] == ["media-ref-1"]
    assert plan.memory_logs_to_create[0].properties["id"] == (
        same_plan.memory_logs_to_create[0].properties["id"]
    )
    assert plan.relationships_to_create[0].relationship_type == "HAS_MEMORY_LOG"
    assert plan.relationships_to_create[0].from_ref == host_id
    assert plan.relationships_to_create[0].to_ref == "MEMORY_LOG_001"
    assert plan.relationships_to_create[0].properties["primary"] is True
    assert plan.relationships_to_create[0].properties["role"] == "primary_host"
    assert result.status == IngestionStatus.WRITTEN
    assert result.metadata["created_memory_logs"] == 1
    assert result.metadata["relationships"] == 1
    assert graph.upserted_nodes[0].label == "MemoryLog"
    assert graph.relationships[0].from_id == host_id
    assert graph.relationships[0].to_id == graph.upserted_nodes[0].properties["id"]


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


def test_executor_rejects_empty_write_plan() -> None:
    plan = GraphWritePlan(source_id="source-1")

    result = GraphWritePlanExecutor(FakeGraphService()).execute(plan)

    assert result.status == IngestionStatus.VALIDATION_FAILED
    assert result.validation_errors[0].code == "empty_write_plan"


def test_ingestion_service_can_execute_fake_write_path() -> None:
    graph = FakeGraphService()
    service = _reasoning_first_service(
        graph=graph,
        provider_payloads=_single_person_payloads("Marco"),
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph),
        execute_write_plan=True,
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.WRITTEN
    assert result.candidate_graph is not None
    assert graph.upserted_nodes[0].label == "Person"


def test_ingestion_service_vectorizes_after_successful_graph_write() -> None:
    graph = FakeGraphService()
    vectorizer = RecordingVectorizer()
    service = _reasoning_first_service(
        graph=graph,
        provider_payloads=_single_person_payloads(
            "Marco",
            description="University friend.",
        ),
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph),
        vectorization_service=vectorizer,
        execute_write_plan=True,
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.WRITTEN
    assert vectorizer.calls == [result.ingestion_id]
    assert result.metadata["vectorization"] == {"status": "ok", "documents_built": 1}


def test_ingestion_service_keeps_written_status_when_vectorization_fails() -> None:
    graph = FakeGraphService()
    service = _reasoning_first_service(
        graph=graph,
        provider_payloads=_single_person_payloads(
            "Marco",
            description="University friend.",
        ),
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph),
        vectorization_service=FailingVectorizer(),
        execute_write_plan=True,
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.WRITTEN
    assert result.metadata["vectorization"]["status"] == "failed"
    assert result.metadata["vectorization"]["error_type"] == "RuntimeError"


def test_ingestion_service_returns_write_plan_ready_when_execution_is_disabled() -> None:
    graph = FakeGraphService()
    service = _reasoning_first_service(
        graph=graph,
        provider_payloads=_single_person_payloads("Marco"),
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph),
        execute_write_plan=False,
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.WRITE_PLAN_READY
    assert result.write_plan is not None
    assert graph.upserted_nodes == []


def test_ingestion_service_rejects_empty_candidate_graph() -> None:
    graph = FakeGraphService()
    service = _reasoning_first_service(
        graph=graph,
        provider_payloads=[
            {
                "summary": "No durable memory candidate.",
                "context_gaps": ["No durable entity or relationship was identified."],
            },
            {"reason": "No entity action needed.", "context_gaps": ["No entity to store."]},
            {
                "reason": "No memory-log action needed.",
                "context_gaps": ["No memory log action needed."],
            },
            {"reason": "No relationship action needed.", "context_gaps": ["No relationship."]},
        ],
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph),
        execute_write_plan=True,
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.VALIDATION_FAILED
    assert result.validation_errors[0].code == "empty_write_plan"


def _reasoning_first_service(
    *,
    graph: "FakeGraphService",
    provider_payloads: Sequence[dict[str, Any]],
    resolution_agent: FixedResolutionAgent | None = None,
    write_plan_builder: GraphWritePlanBuilder | None = None,
    write_plan_executor: GraphWritePlanExecutor | None = None,
    vectorization_service: Any | None = None,
    execute_write_plan: bool = False,
) -> IngestionService:
    provider = QueuedStructuredProvider(provider_payloads)
    runner = AgenticStateRunner(provider=provider)
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    registry.register_owner("person:owner")
    context_pack = GraphContextPack(
        source_id="source-1",
        alias_map=registry.backend_alias_map(),
        reference_registry_snapshot=registry.snapshot(),
    )
    return IngestionService(
        reasoning_service=AgenticReasoningService(runner),
        planning_service=AgenticPlanningService(runner),
        graph_context_builder=StaticGraphContextBuilder(context_pack),
        entity_extractors=[EntityExtractor(provider)],
        relationship_extractors=[RelationshipExtractor(provider)],
        resolution_agent=resolution_agent or FixedResolutionAgent(),
        write_plan_builder=write_plan_builder,
        write_plan_executor=write_plan_executor,
        vectorization_service=vectorization_service,
        execute_write_plan=execute_write_plan,
    )


def _single_person_payloads(
    display_name: str,
    *,
    description: str | None = None,
) -> list[dict[str, Any]]:
    candidate: dict[str, Any] = {
        "local_ref": "CANDIDATE_PERSON_001",
        "entity_type": "Person",
        "display_name": display_name,
    }
    if description:
        candidate["description"] = description
    return [
        {
            "summary": f"The source introduces {display_name}.",
            "entity_notes": [f"{display_name} should be handled as a person candidate."],
        },
        {
            "reason": f"{display_name} is a person endpoint.",
            "actions": [
                {
                    "goal": f"Extract {display_name} as a person.",
                    "entities": [
                        {
                            "local_ref": "CANDIDATE_PERSON_001",
                            "mention_text": display_name,
                            "suggested_entity_type": "Person",
                            "evidence_text": display_name,
                        },
                    ],
                }
            ],
        },
        {"candidates": [candidate]},
        {
            "reason": "No memory-log action is needed for this single-person fixture.",
            "context_gaps": ["No memory log action needed."],
        },
        {"reason": "No relationship action needed.", "context_gaps": ["No relationship."]},
    ]


class QueuedStructuredProvider:
    provider_name = "fake"

    def __init__(self, payloads: Sequence[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[StructuredGenerationRequest] = []

    def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredGenerationResult:
        self.requests.append(request)
        payload = self.payloads.pop(0)
        parsed = request.output_schema.model_validate(payload)
        return StructuredGenerationResult(
            parsed=parsed,
            metadata=ProviderCallMetadata.fake(model=request.model or "fake-model"),
        )


class StaticGraphContextBuilder:
    def __init__(self, pack: GraphContextPack) -> None:
        self.pack = pack

    def build(self, source: SourceRecordRef) -> GraphContextPack:
        return self.pack.model_copy(update={"source_id": source.source_id}, deep=True)


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


class RecordingVectorizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def vectorize_ingestion_result(self, result):
        self.calls.append(result.ingestion_id)
        return {"status": "ok", "documents_built": 1}


class FailingVectorizer:
    def vectorize_ingestion_result(self, result):
        raise RuntimeError("chroma unavailable")


def _candidate_graph(
    candidates: Sequence[CandidateOutput],
    *,
    memory_logs: Sequence[MemoryLog] = (),
):
    graph = CandidateMemoryGraphAssembler().assemble(_source(), _plan(), candidates)
    if memory_logs:
        return graph.model_copy(update={"memory_logs": list(memory_logs)}, deep=True)
    return graph


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
