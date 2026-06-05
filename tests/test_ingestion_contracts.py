from __future__ import annotations

from collections.abc import Sequence

from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.contracts import (
    AffectiveFields,
    CandidateEntity,
    CandidateOutput,
    CandidateRelationship,
    ClarificationRequest,
    EvidenceRef,
    ExtractionPlan,
    ExtractionTask,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    IngestionContextPackage,
    Mention,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import (
    ExtractionExecutionMode,
    ExtractionTaskType,
    IngestionStatus,
    MentionKind,
    SourceChannel,
    SourceType,
)
from my_digital_brain.ingestion.protocols import (
    FocusedExtractor,
    IngestionContextRetriever,
    IngestionPlanner,
    MentionScanner,
)
from my_digital_brain.ingestion.service import IngestionService
from my_digital_brain.ingestion.validation import IngestionValidator


def test_ingestion_contracts_accept_rich_factual_and_affective_candidates() -> None:
    source = _source()
    evidence = EvidenceRef(
        source_id=source.source_id,
        evidence_text="I met Marco in Milan and felt happy.",
    )
    candidate = CandidateEntity(
        local_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        display_name="Marco",
        description="A friend mentioned in a memory about Milan.",
        affective_fields=AffectiveFields(
            emotional_summary="The memory carries warmth.",
            emotional_valence="positive",
            emotional_intensity=0.7,
            emotion_tags=["warmth"],
            original_user_words="felt happy",
        ),
        source_refs=[source.source_id],
        evidence_refs=[evidence],
    )

    dumped = candidate.model_dump(mode="json", exclude_none=True)

    assert dumped["entity_type"] == "Person"
    assert dumped["affective_fields"]["emotional_summary"] == "The memory carries warmth."
    assert dumped["evidence_refs"][0]["source_id"] == source.source_id


def test_candidate_graph_assembler_splits_outputs_and_preserves_local_refs() -> None:
    source = _source()
    plan = _plan()
    person = CandidateEntity(
        local_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        display_name="Marco",
        source_refs=[source.source_id],
    )
    place = CandidateEntity(
        local_ref="CANDIDATE_PLACE_001",
        entity_type="Place",
        display_name="Milan",
        source_refs=[source.source_id],
    )
    relationship = CandidateRelationship(
        local_ref="CANDIDATE_REL_001",
        relationship_type="HAPPENED_AT",
        from_ref="CANDIDATE_PERSON_001",
        to_ref="CANDIDATE_PLACE_001",
        source_refs=[source.source_id],
    )

    graph = CandidateMemoryGraphAssembler().assemble(
        source,
        plan,
        [person, place, relationship],
    )

    assert len(graph.candidate_entities) == 2
    assert graph.local_ref_map["CANDIDATE_PERSON_001"] == person.candidate_id
    assert graph.candidate_relationships[0].relationship_type == "HAPPENED_AT"


def test_candidate_graph_assembler_remaps_duplicate_local_refs_before_validation() -> None:
    source = _source()
    plan = _plan()
    first_person = CandidateEntity(
        local_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        display_name="Marco",
        source_refs=[source.source_id],
        metadata={"task_id": "task-person"},
    )
    second_person = CandidateEntity(
        local_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        display_name="Marco Rossi",
        source_refs=[source.source_id],
        metadata={"task_id": "task-person-detail"},
    )

    graph = CandidateMemoryGraphAssembler().assemble(
        source,
        plan,
        [first_person, second_person],
    )
    result = IngestionValidator().validate_candidate_graph(graph)

    assert result.is_valid is True
    assert graph.candidate_entities[0].local_ref == "CANDIDATE_PERSON_001"
    assert graph.candidate_entities[1].local_ref.startswith("CANDIDATE_PERSON_001_TASK_")
    assert graph.candidate_entities[1].metadata["original_local_ref"] == "CANDIDATE_PERSON_001"


def test_candidate_graph_validation_uses_graph_registries_and_refs() -> None:
    source = _source()
    plan = _plan()
    candidate_graph = CandidateMemoryGraphAssembler().assemble(
        source,
        plan,
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="UnsafeLabel",
                source_refs=[source.source_id],
            ),
            CandidateRelationship(
                local_ref="CANDIDATE_REL_001",
                relationship_type="UNSAFE_REL",
                from_ref="CANDIDATE_PERSON_001",
                to_ref="CANDIDATE_PLACE_404",
                source_refs=[source.source_id],
            ),
        ],
    )

    result = IngestionValidator().validate_candidate_graph(candidate_graph)
    codes = {issue.code for issue in result.issues}

    assert result.is_valid is False
    assert "unsupported_node_label" in codes
    assert "unsupported_relationship_type" in codes
    assert "unknown_candidate_ref" in codes


def test_candidate_graph_validation_requires_candidate_evidence_or_source_refs() -> None:
    source = _source()
    candidate_graph = CandidateMemoryGraphAssembler().assemble(
        source,
        _plan(),
        [
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco",
            ),
        ],
    )

    result = IngestionValidator().validate_candidate_graph(candidate_graph)

    assert result.is_valid is False
    assert result.issues[0].code == "missing_candidate_evidence"


def test_write_plan_validation_rejects_unknown_labels_types_and_endpoints() -> None:
    write_plan = GraphWritePlan(
        source_id="source-1",
        nodes_to_create=[
            GraphNodeWrite(local_ref="CANDIDATE_PERSON_001", label="Person"),
            GraphNodeWrite(local_ref="CANDIDATE_BAD_001", label="UnsafeLabel"),
        ],
        relationships_to_create=[
            GraphRelationshipWrite(
                local_ref="CANDIDATE_REL_001",
                relationship_type="NOT_ALLOWED",
                from_ref="CANDIDATE_PERSON_001",
                to_ref="CANDIDATE_PLACE_404",
            ),
        ],
    )

    result = IngestionValidator().validate_write_plan(write_plan)
    codes = {issue.code for issue in result.issues}

    assert result.is_valid is False
    assert "unsupported_node_label" in codes
    assert "unsupported_relationship_type" in codes
    assert "unknown_write_endpoint" in codes


def test_ingestion_service_runs_pluggable_contract_pipeline() -> None:
    source = _source()
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
                        source_refs=[source.source_id],
                    ),
                ],
            ),
        ],
    )

    result = service.process_source(source)

    assert result.status == IngestionStatus.CANDIDATE_READY
    assert result.candidate_graph is not None
    assert result.candidate_graph.candidate_entities[0].display_name == "Marco"


def test_ingestion_service_returns_clarification_without_extraction() -> None:
    source = _source()
    plan = ExtractionPlan(
        source_id=source.source_id,
        execution_mode=ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST,
        clarification=ClarificationRequest(
            question="Which Marco?",
            reason="Multiple known people may match this mention.",
            target_refs=["CANDIDATE_PERSON_001"],
        ),
    )
    service = IngestionService(
        scanner=StaticScanner(),
        context_retriever=StaticContextRetriever(),
        planner=StaticPlanner(plan),
    )

    result = service.process_source(source)

    assert result.status == IngestionStatus.NEEDS_CLARIFICATION
    assert result.clarification is not None
    assert result.clarification.question == "Which Marco?"


def test_ingestion_service_reports_missing_extractor_as_verbose_tool_error() -> None:
    source = _source()
    service = IngestionService(
        scanner=StaticScanner(),
        context_retriever=StaticContextRetriever(),
        planner=StaticPlanner(_plan()),
    )

    result = service.process_source(source)

    assert result.status == IngestionStatus.VALIDATION_FAILED
    assert result.validation_errors[0].code == "missing_focused_extractor"
    assert "Register a backend extractor" in result.validation_errors[0].message


def test_ingestion_components_match_runtime_protocols() -> None:
    assert isinstance(StaticScanner(), MentionScanner)
    assert isinstance(StaticContextRetriever(), IngestionContextRetriever)
    assert isinstance(StaticPlanner(_plan()), IngestionPlanner)
    assert isinstance(StaticExtractor([]), FocusedExtractor)


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


def _source() -> SourceRecordRef:
    return SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Marco in Milan and felt happy.",
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
