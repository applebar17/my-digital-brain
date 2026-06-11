from __future__ import annotations

from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.contracts import (
    AffectiveFields,
    CandidateEntity,
    CandidateEntityDraft,
    CandidateOutput,
    CandidateRelationship,
    ClarificationRequest,
    EntityIngestionActionDraft,
    EntityIngestionPlanDraft,
    EvidenceRef,
    ExtractionPlan,
    ExtractionTask,
    GraphContextDuplicateHintItem,
    GraphContextEntityItem,
    GraphContextKnownAliasItem,
    GraphContextMemoryItem,
    GraphContextPack,
    GraphContextPackView,
    GraphContextRelationshipItem,
    GraphContextRelationshipSnippetItem,
    GraphContextRenderPurpose,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    IngestionContextPackage,
    IngestionReasoningCheckpointDraft,
    MediaAsset,
    MediaAssetRefDraft,
    MemoryLog,
    MemoryLogDraft,
    MemoryLogImportance,
    MemoryLogKind,
    MemoryLogLink,
    MemoryLogLinkDraft,
    MemoryLogSourceKind,
    MissingEntityRequiredDraft,
    MultiScopeRetrievalResult,
    MultiScopeVectorConfig,
    NodeUpdatePlanDraft,
    RelationshipIngestionActionDraft,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
    ResolvedEntityMapEntry,
    ResolvedEntityStatus,
    SourceRecordRef,
    V1_VECTOR_DIMENSIONS,
    VectorQueryStrategy,
    VectorScopeConfig,
    VectorScopeHitRef,
    VectorScopeName,
    VectorScopeSearchRequest,
)
from my_digital_brain.ingestion.enums import (
    ExtractionExecutionMode,
    ExtractionTaskType,
    IngestionStatus,
    SourceChannel,
    SourceType,
)
from my_digital_brain.ingestion.protocols import (
    FocusedExtractor,
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


def test_ingestion_components_match_runtime_protocols() -> None:
    assert isinstance(StaticExtractor([]), FocusedExtractor)


def test_graph_context_pack_is_backend_owned_and_view_is_llm_friendly() -> None:
    pack = GraphContextPack(
        source_id="source-1",
        retrieval_strategy="whole_source_hybrid",
        compact_summary="Context around Matteo Mercoldi and his known aliases.",
        known_aliases=[
            GraphContextKnownAliasItem(
                alias="Merc",
                target_ref="graph:person:matteo",
                source_id="source-1",
                retrieval_strategy="alias_lookup",
            ),
        ],
        entities=[
            GraphContextEntityItem(
                ref="graph:person:matteo",
                display_label="Matteo Mercoldi",
                entity_type="Person",
                compact_summary="A person known by the alias Merc.",
                aliases=["Merc"],
                source_id="source-1",
                retrieval_strategy="hybrid",
                score=0.98,
            ),
        ],
        relationships=[
            GraphContextRelationshipItem(
                ref="rel:friend",
                from_ref="graph:person:user",
                to_ref="graph:person:matteo",
                relationship_type="RELATIONSHIP_WITH",
                relationship_detail="friend",
                source_id="source-1",
                retrieval_strategy="hybrid",
            ),
        ],
        memories=[
            GraphContextMemoryItem(
                ref="memory:1",
                compact_summary="The user mentioned Merc as Matteo Mercoldi.",
                related_refs=["graph:person:matteo"],
                source_id="source-1",
                retrieval_strategy="history",
            ),
        ],
        duplicate_hints=[
            GraphContextDuplicateHintItem(
                candidate_text="Merc",
                possible_match_refs=["graph:person:matteo"],
                reason="Alias match.",
                score=0.92,
                source_id="source-1",
                retrieval_strategy="alias_lookup",
            ),
        ],
        relationship_context_snippets=[
            GraphContextRelationshipSnippetItem(
                ref="snippet:1",
                endpoint_refs=["graph:person:user", "graph:person:matteo"],
                compact_summary="Merc appears as Matteo in prior context.",
                source_id="source-1",
                retrieval_strategy="nearby_context",
            ),
        ],
    )
    view = GraphContextPackView(
        purpose=GraphContextRenderPurpose.ENTITY_PLANNING,
        compact_summary=pack.compact_summary,
        aliases=["Merc -> Matteo Mercoldi"],
        selected_entities=["Matteo Mercoldi (Person): known as Merc."],
        selected_relationships=["User relationship with Matteo: friend."],
        duplicate_hints=["Merc may match Matteo Mercoldi."],
        relationship_context_snippets=["Merc appears as Matteo in prior context."],
        notes=["Use aliases as hints only."],
    )
    rendered = view.model_dump(mode="json", exclude_none=True)

    assert pack.source_id == "source-1"
    assert pack.entities[0].source_id == "source-1"
    assert rendered["purpose"] == "entity_planning"
    assert "source_id" not in rendered
    assert "retrieval_strategy" not in rendered
    assert "source_id" not in GraphContextPackView.model_fields
    assert "retrieval_strategy" not in GraphContextPackView.model_fields


def test_lightweight_ingestion_reasoning_and_plan_drafts_validate_signal() -> None:
    reasoning = IngestionReasoningCheckpointDraft(
        summary="Merc likely refers to Matteo Mercoldi.",
        alias_notes=["Merc is an alias hint for Matteo Mercoldi."],
    )
    entity_plan = EntityIngestionPlanDraft(
        reason="The source names a person with an alias.",
        actions=[
            EntityIngestionActionDraft(
                action_ref="ENTITY_ACTION_001",
                goal="Extract Matteo Mercoldi as a person candidate.",
                mention_text="Matteo Mercoldi",
                suggested_entity_type="Person",
                aliases=["Merc"],
                evidence_text="Merc is Matteo Mercoldi.",
            ),
        ],
    )
    missing = MissingEntityRequiredDraft(
        missing_ref="MISSING_ENTITY_001",
        reason="The relationship endpoint has not been resolved yet.",
        mention_text="mio fratello",
        suggested_entity_type="Person",
        needed_for_relationship_ref="REL_ACTION_001",
        relationship_goal="Represent the brother relationship.",
        relationship_endpoint_role="to",
        evidence_text="mio fratello vive a Milano",
        entity_planning_guidance="Plan extraction for the brother endpoint.",
        relationship_resume_guidance="Resume the brother relationship after resolution.",
    )
    relationship_plan = RelationshipIngestionPlanDraft(
        reason="A relationship is present but needs one endpoint.",
        missing_entities=[missing],
    )

    assert reasoning.alias_notes == ["Merc is an alias hint for Matteo Mercoldi."]
    assert entity_plan.actions[0].aliases == ["Merc"]
    assert relationship_plan.missing_entities[0].missing_ref == "MISSING_ENTITY_001"

    with pytest.raises(ValidationError, match="at least one note"):
        IngestionReasoningCheckpointDraft(summary="Only a summary.")
    with pytest.raises(ValidationError, match="requires actions"):
        EntityIngestionPlanDraft(reason="No next step.")
    with pytest.raises(ValidationError, match="requires actions"):
        RelationshipIngestionPlanDraft(reason="No next step.")


def test_relationship_plan_accepts_simple_actions_and_missing_entity_blockers() -> None:
    plan = RelationshipIngestionPlanDraft(
        reason="Resolved refs allow a direct relationship action.",
        actions=[
            RelationshipIngestionActionDraft(
                action_ref="REL_ACTION_001",
                goal="Connect the user with the brother entity.",
                from_ref="graph:user",
                to_ref="CANDIDATE_PERSON_001",
                relationship_intent="The candidate is the user's brother.",
                storage_shape="direct_relationship",
                evidence_text="mio fratello",
            ),
        ],
    )

    assert plan.actions[0].relationship_intent == "The candidate is the user's brother."


def test_resolved_entity_map_marks_relationship_usable_refs() -> None:
    resolved_map = ResolvedEntityMap(
        entries=[
            ResolvedEntityMapEntry(
                local_ref="CANDIDATE_PERSON_001",
                status=ResolvedEntityStatus.MATCHED_EXISTING,
                display_label="Matteo Mercoldi",
                entity_type="Person",
                graph_alias="graph:person:matteo",
            ),
            ResolvedEntityMapEntry(
                local_ref="CANDIDATE_PLACE_001",
                status=ResolvedEntityStatus.STAGED_CREATE,
                display_label="Milan",
                entity_type="Place",
            ),
            ResolvedEntityMapEntry(
                local_ref="CANDIDATE_PERSON_002",
                status=ResolvedEntityStatus.PENDING_DUPLICATE_REVIEW,
                display_label="Merc",
                entity_type="Person",
                duplicate_notes=["Could duplicate Matteo Mercoldi."],
            ),
            ResolvedEntityMapEntry(
                local_ref="CANDIDATE_BAD_001",
                status=ResolvedEntityStatus.REJECTED,
                display_label="unsupported",
                entity_type="Unknown",
            ),
        ],
    )

    assert resolved_map.relationship_usable_refs == {
        "CANDIDATE_PERSON_001": "graph:person:matteo",
        "CANDIDATE_PLACE_001": "CANDIDATE_PLACE_001",
    }
    assert resolved_map.relationship_ref_for("CANDIDATE_PERSON_002") is None
    assert resolved_map.entry_for("CANDIDATE_BAD_001") is not None


def test_candidate_entity_alias_schema_locks_hint_semantics() -> None:
    description = CandidateEntityDraft.model_fields["aliases"].description or ""
    draft = CandidateEntityDraft(
        local_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        aliases=["Merc"],
    )

    assert draft.aliases == ["Merc"]
    assert "hints" in description
    assert "do not define node identity" in description
    assert "not automatically writable node properties" in description


def test_memory_log_draft_requires_host_and_primary_for_multiple_hosts() -> None:
    draft = MemoryLogDraft(
        local_ref="MEMORY_LOG_001",
        log_text="Marco said yesterday that he changed job.",
        log_kind=MemoryLogKind.UPDATE,
        host_refs=[
            MemoryLogLinkDraft(target_ref="graph:person:marco", primary=True),
            MemoryLogLinkDraft(target_ref="graph:person:luca", role="mentioned"),
        ],
        involved_refs=[MemoryLogLinkDraft(target_ref="graph:place:athens", role="place")],
        media_refs=[
            MediaAssetRefDraft(
                media_ref="local:photo-1",
                role="memory_photo",
                caption_hint="Marco and Luca in Athens.",
            ),
        ],
        source_kind=MemoryLogSourceKind.USER_STATED,
        importance=MemoryLogImportance.LOW,
    )

    assert draft.host_refs[0].primary is True
    assert draft.media_refs[0].media_ref == "local:photo-1"

    with pytest.raises(ValidationError, match="at least one host_ref"):
        MemoryLogDraft(local_ref="MEMORY_LOG_002", log_text="No host.")
    with pytest.raises(ValidationError, match="exactly one primary host"):
        MemoryLogDraft(
            local_ref="MEMORY_LOG_003",
            log_text="Two hosts but no primary.",
            host_refs=[
                MemoryLogLinkDraft(target_ref="graph:person:marco"),
                MemoryLogLinkDraft(target_ref="graph:person:luca"),
            ],
        )


def test_memory_log_backend_record_supports_multiple_hosts_and_media_asset() -> None:
    log = MemoryLog(
        local_ref="MEMORY_LOG_001",
        log_text="Marco and Luca got a beer in Athens.",
        log_kind=MemoryLogKind.EVENT_DETAIL,
        primary_host_target_id="node-marco",
        host_target_ids=["node-marco", "node-luca"],
        involved_target_ids=["node-athens"],
        links=[
            MemoryLogLink(
                target_id="node-marco",
                target_label="Person",
                relationship_type="HAS_MEMORY_LOG",
                primary=True,
            ),
            MemoryLogLink(
                target_id="node-luca",
                target_label="Person",
                relationship_type="HAS_MEMORY_LOG",
            ),
            MemoryLogLink(
                target_id="node-athens",
                target_label="Place",
                relationship_type="INVOLVES",
                role="place",
            ),
        ],
        media_refs=["media-1"],
    )
    media = MediaAsset(
        media_asset_id="media-1",
        media_type="image",
        storage_key="photos/athens.jpg",
        checksum="sha256:abc",
        caption="Athens aperitivo.",
    )

    assert log.primary_host_target_id == "node-marco"
    assert log.links[0].primary is True
    assert media.media_type == "image"

    with pytest.raises(ValidationError, match="requires at least one host target"):
        MemoryLog(log_text="Orphan log.")
    with pytest.raises(ValidationError, match="at most one primary"):
        MemoryLog(
            log_text="Two primary links.",
            links=[
                MemoryLogLink(
                    target_id="node-1",
                    relationship_type="HAS_MEMORY_LOG",
                    primary=True,
                ),
                MemoryLogLink(
                    target_id="node-2",
                    relationship_type="HAS_MEMORY_LOG",
                    primary=True,
                ),
            ],
        )


def test_node_update_plan_prefers_memory_logs_but_allows_safe_patches() -> None:
    plan = NodeUpdatePlanDraft(
        reason="The source gives a short update about Marco.",
        memory_logs=[
            MemoryLogDraft(
                local_ref="MEMORY_LOG_001",
                log_text="Marco now lives in Turin.",
                log_kind=MemoryLogKind.UPDATE,
                host_refs=[MemoryLogLinkDraft(target_ref="graph:person:marco", primary=True)],
            ),
        ],
    )

    assert plan.memory_logs[0].log_text == "Marco now lives in Turin."

    with pytest.raises(ValidationError, match="requires memory_logs"):
        NodeUpdatePlanDraft(reason="No update action.")


def test_vector_scope_config_locks_v1_shared_512_dimensions() -> None:
    scopes = [
        VectorScopeConfig(
            scope=VectorScopeName.MEMORY_NODE_SUMMARIES,
            collection="memory_node_summaries",
            dimensions=V1_VECTOR_DIMENSIONS,
        ),
        VectorScopeConfig(
            scope=VectorScopeName.MEMORY_CONTEXTS,
            collection="memory_contexts",
            dimensions=V1_VECTOR_DIMENSIONS,
        ),
        VectorScopeConfig(
            scope=VectorScopeName.MEMORY_MICRO_LOGS,
            collection="memory_micro_logs",
            dimensions=V1_VECTOR_DIMENSIONS,
        ),
    ]
    config = MultiScopeVectorConfig(
        query_strategy=VectorQueryStrategy.SINGLE_SHARED_DIMENSION,
        dimensions=V1_VECTOR_DIMENSIONS,
        scopes=scopes,
    )
    request = VectorScopeSearchRequest(
        query_text="Marco changed job",
        enabled_scopes=[VectorScopeName.MEMORY_MICRO_LOGS],
    )
    result = MultiScopeRetrievalResult(
        query_text="Marco changed job",
        hits=[
            VectorScopeHitRef(
                scope=VectorScopeName.MEMORY_MICRO_LOGS,
                collection="memory_micro_logs",
                vector_id="memory_micro_logs:memory_log_summary:log-1",
                score=0.92,
                primary_target_id="log-1",
                primary_target_label="MemoryLog",
                canonical_target_id="node-marco",
                related_target_ids=["node-marco"],
                hit_role="memory_log",
            ),
        ],
    )

    assert config.dimensions == 512
    assert request.dimensions == 512
    assert result.hits[0].canonical_target_id == "node-marco"

    with pytest.raises(ValidationError, match="must be 512"):
        VectorScopeConfig(
            scope=VectorScopeName.MEMORY_MICRO_LOGS,
            collection="memory_micro_logs",
            dimensions=256,
        )
    with pytest.raises(ValidationError, match="single_shared_dimension"):
        MultiScopeVectorConfig(
            query_strategy=VectorQueryStrategy.PER_SCOPE_EMBEDDING,
            scopes=scopes,
        )


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
