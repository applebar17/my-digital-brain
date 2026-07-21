from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from my_digital_brain.agentic import (
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticStateRunner,
)
from my_digital_brain.ai.schemas import ProviderCallMetadata, StructuredGenerationRequest
from my_digital_brain.ai.schemas import StructuredGenerationResult
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.ingestion import (
    IngestionService,
    WholeSourceGraphContextPackBuilder,
)
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    GraphContextDuplicateHintItem,
    GraphContextEntityItem,
    GraphContextKnownAliasItem,
    GraphContextPack,
    GraphContextRelationshipItem,
    GraphContextRelationshipSnippetItem,
    ResolvedEntityStatus,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import IngestionStatus, SourceChannel, SourceType
from my_digital_brain.ingestion.extractors import EntityExtractor, RelationshipExtractor
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.runtime_helpers import batch_sequence as _batch_sequence
from tests.support_resolution import FixedResolutionAgent


def test_extraction_draft_batches_fold_trailing_singleton() -> None:
    batches = _batch_sequence(list(range(19)), 3)

    assert [len(batch) for batch in batches] == [3, 3, 3, 3, 3, 4]
    assert [item for batch in batches for item in batch] == list(range(19))
    assert [len(batch) for batch in _batch_sequence(list(range(21)), 99)] == [10, 10, 1]


def test_whole_source_graph_context_pack_builder_compacts_hybrid_search_result() -> None:
    source = _source("Merc is Matteo Mercoldi.")
    service = FakeSearchService(
        {
            "hits": [
                {
                    "score": 0.98,
                    "source": "semantic",
                    "primary_target_id": "person-matteo",
                    "primary_target_label": "Person",
                    "title": "Matteo Mercoldi",
                    "description": "Known by the nickname Merc.",
                    "source_ids": ["source-old"],
                    "target": {
                        "id": "person-matteo",
                        "label": "Person",
                        "title": "Matteo Mercoldi",
                        "display_metadata": {"aliases": ["Merc"]},
                    },
                },
            ],
            "graph_view": {
                "relationships": [
                    {
                        "id": "rel-family",
                        "type": "RELATIONSHIP_WITH",
                        "from_id": "owner",
                        "to_id": "person-matteo",
                        "description": "family context",
                    },
                ],
            },
            "context_packages": [
                {
                    "relationship_contexts": [
                        {
                            "id": "ctx-1",
                            "description": "Merc appears in family wording.",
                            "endpoint_refs": ["owner", "person-matteo"],
                        },
                    ],
                },
            ],
        },
    )

    pack = WholeSourceGraphContextPackBuilder(search_service=service).build(source)

    assert service.calls == [{"query": "Merc is Matteo Mercoldi.", "limit": 10}]
    assert pack.retrieval_strategy == "whole_source_hybrid"
    assert pack.entities[0].ref == "NODE_000001"
    assert pack.entities[0].display_label == "Matteo Mercoldi"
    assert pack.known_aliases[0].alias == "Merc"
    assert pack.duplicate_hints[0].possible_match_refs == ["NODE_000001"]
    assert pack.relationships[0].to_ref == "NODE_000001"
    assert pack.relationship_context_snippets[0].compact_summary == (
        "Merc appears in family wording."
    )


def test_reasoning_first_runtime_matches_merc_alias_to_existing_entity_before_relationship_planning() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "summary": "Merc likely refers to Matteo Mercoldi.",
                "alias_notes": ["Merc is an alias hint for Matteo Mercoldi."],
            },
            {
                "reason": "The source names Matteo and his alias.",
                "actions": [
                    {
                        "goal": "Extract Matteo Mercoldi as one person candidate.",
                        "entities": [
                            {
                                "local_ref": "CANDIDATE_PERSON_001",
                                "mention_text": "Matteo Mercoldi",
                                "suggested_entity_type": "Person",
                                "aliases": ["Merc"],
                                "evidence_text": "Merc is Matteo Mercoldi.",
                            },
                        ],
                    },
                ],
            },
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "Matteo Mercoldi",
                        "aliases": ["Merc"],
                    },
                ],
            },
            {
                "reason": "No episodic memory log is needed for this alias-only source.",
                "context_gaps": ["No memory log action needed."],
            },
            {
                "reason": "No relationship action is needed from this source.",
                "context_gaps": ["No relationship action needed."],
            },
        ],
    )
    result = _service(provider, _matteo_pack()).process_source(
        _source("Merc is Matteo Mercoldi."),
    )

    assert result.status == IngestionStatus.CANDIDATE_READY
    assert result.reasoning is not None
    assert result.entity_plan is not None
    assert result.resolved_entity_map is not None
    assert result.resolved_entity_map.entries[0].status == (
        ResolvedEntityStatus.MATCHED_EXISTING.value
    )
    assert result.resolved_entity_map.entries[0].graph_alias == "NODE_000001"
    assert result.relationship_plan is not None
    assert result.relationship_extraction_plan is not None
    assert result.relationship_extraction_plan.tasks == []
    assert result.candidate_graph is not None
    assert result.candidate_graph.candidate_entities
    assert provider.requests[0].output_schema.__name__ == "IngestionReasoningCheckpointDraft"
    assert provider.requests[1].output_schema.__name__ == "EntityIngestionPlanDraft"
    assert provider.requests[2].output_schema.__name__ == "CandidateEntityDraftBatch"
    assert provider.requests[3].output_schema.__name__ == "MemoryLogIngestionPlanDraft"
    assert provider.requests[4].output_schema.__name__ == "RelationshipIngestionPlanDraft"


def test_reasoning_first_runtime_plans_brother_relationship_against_staged_entity_ref() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "summary": "The source introduces Lorenzo and a brother relationship.",
                "entity_notes": ["Lorenzo should be an entity candidate."],
                "relationship_notes": ["Brother wording should become relationship detail."],
            },
            {
                "reason": "Lorenzo is a named person endpoint.",
                "actions": [
                    {
                        "goal": "Extract Lorenzo as a person candidate.",
                        "entities": [
                            {
                                "local_ref": "CANDIDATE_PERSON_001",
                                "mention_text": "Lorenzo",
                                "suggested_entity_type": "Person",
                                "evidence_text": "my brother Lorenzo",
                            },
                        ],
                    },
                ],
            },
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "Lorenzo",
                    },
                ],
            },
            {
                "reason": "The source has an episodic update about Lorenzo.",
                "actions": [
                    {
                        "goal": "Store the Lorenzo living detail as a compact memory.",
                        "memory_logs": [
                            {
                                "local_ref": "MEMORY_LOG_001",
                                "log_text_hint": "Lorenzo lives in Milan.",
                                "host_refs": ["CANDIDATE_PERSON_001"],
                                "evidence_text": "my brother Lorenzo lives in Milan",
                            }
                        ],
                    }
                ],
            },
            {
                "candidates": [
                    {
                        "local_ref": "MEMORY_LOG_MODEL_001",
                        "log_text": "Lorenzo lives in Milan.",
                        "log_kind": "event_detail",
                        "host_refs": [
                            {
                                "target_ref": "CANDIDATE_PERSON_001",
                                "primary": True,
                            }
                        ],
                        "evidence": [
                            {
                                "evidence_text": "my brother Lorenzo lives in Milan",
                            }
                        ],
                    }
                ],
            },
            {
                "reason": "The resolved entity map provides Lorenzo as a staged ref.",
                "actions": [
                    {
                        "local_ref": "CANDIDATE_RELATIONSHIP_001",
                        "goal": "Plan the user-to-Lorenzo brother relationship.",
                        "from_ref": "OWNER",
                        "to_ref": "CANDIDATE_PERSON_001",
                        "relationship_intent": "Lorenzo is the user's brother.",
                        "storage_shape": "direct_relationship",
                        "evidence_text": "my brother Lorenzo",
                    },
                ],
            },
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_RELATIONSHIP_001",
                        "relationship_type": "RELATIONSHIP_WITH",
                        "from_ref": "OWNER",
                        "to_ref": "CANDIDATE_PERSON_001",
                        "relationship_kind": "family",
                        "relationship_detail": "brother",
                    },
                ],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("My brother Lorenzo lives in Milan."),
    )

    assert result.status == IngestionStatus.CANDIDATE_READY
    assert result.resolved_entity_map is not None
    assert result.resolved_entity_map.relationship_usable_refs == {
        "CANDIDATE_PERSON_001": "CANDIDATE_PERSON_001",
    }
    assert result.relationship_plan is not None
    assert result.relationship_plan.actions[0].to_ref == "CANDIDATE_PERSON_001"
    assert result.relationship_plan.actions[0].relationship_intent == (
        "Lorenzo is the user's brother."
    )
    assert result.relationship_extraction_plan is not None
    assert result.relationship_extraction_plan.tasks[0].task_type == "relationship"
    assert result.memory_log_plan is not None
    assert len(result.memory_logs) == 1
    assert result.memory_logs[0].local_ref == "MEMORY_LOG_001"
    assert result.memory_logs[0].metadata["model_output_local_ref"] == (
        "MEMORY_LOG_MODEL_001"
    )
    assert len(result.relationship_candidates) == 1
    assert result.candidate_graph is not None
    assert len(result.candidate_graph.memory_logs) == 1
    assert len(result.candidate_graph.candidate_relationships) == 1


def test_reasoning_first_runtime_resolves_missing_entity_before_relationship_candidates() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "summary": "The source has brother wording but no named endpoint.",
                "relationship_notes": ["The brother endpoint is missing."],
            },
            {
                "reason": "No named entity endpoint was explicit enough.",
                "context_gaps": ["No named brother endpoint was found."],
            },
            {
                "reason": "No memory log is planned until the missing endpoint is resolved.",
                "context_gaps": ["Missing relationship endpoint blocks useful memory hosting."],
            },
            {
                "reason": "The brother relationship is blocked by a missing endpoint.",
                "missing_entities": [
                    {
                        "missing_ref": "MISSING_ENTITY_001",
                        "reason": "The brother endpoint is required.",
                        "mention_text": "my brother",
                        "suggested_entity_type": "Person",
                        "needed_for_relationship_ref": "CANDIDATE_RELATIONSHIP_001",
                        "relationship_goal": "Represent the user's brother relationship.",
                        "relationship_endpoint_role": "to",
                        "evidence_text": "my brother",
                        "entity_planning_guidance": "Plan one person endpoint for the brother.",
                        "relationship_resume_guidance": (
                            "Resume CANDIDATE_RELATIONSHIP_001 after resolution."
                        ),
                    },
                ],
            },
            {
                "reason": "The missing brother endpoint must be prepared first.",
                "actions": [
                    {
                        "goal": "Extract the user's brother as a person endpoint.",
                        "entities": [
                            {
                                "local_ref": "CANDIDATE_PERSON_001",
                                "mention_text": "my brother",
                                "suggested_entity_type": "Person",
                                "evidence_text": "my brother",
                            },
                        ],
                    },
                ],
            },
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "The user's brother",
                    },
                ],
            },
            {
                "reason": "The supplemental entity map now has the brother endpoint.",
                "actions": [
                    {
                        "local_ref": "CANDIDATE_RELATIONSHIP_001",
                        "goal": "Represent the user's brother relationship.",
                        "from_ref": "OWNER",
                        "to_ref": "CANDIDATE_PERSON_001",
                        "relationship_intent": "The unnamed person is the user's brother.",
                        "storage_shape": "direct_relationship",
                        "evidence_text": "my brother",
                    },
                ],
            },
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_RELATIONSHIP_001",
                        "relationship_type": "RELATIONSHIP_WITH",
                        "from_ref": "OWNER",
                        "to_ref": "CANDIDATE_PERSON_001",
                        "relationship_kind": "family",
                        "relationship_detail": "brother",
                    },
                ],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("My brother lives in Milan."),
    )

    assert result.status == IngestionStatus.CANDIDATE_READY
    assert result.entity_candidates == []
    assert result.resolved_entity_map is not None
    assert result.resolved_entity_map.relationship_usable_refs == {
        "CANDIDATE_PERSON_001": "CANDIDATE_PERSON_001",
    }
    assert len(result.supplemental_entity_candidates) == 1
    assert result.relationship_plan is not None
    assert result.relationship_plan.missing_entities == []
    assert len(result.relationship_candidates) == 1
    assert len(provider.requests) == 8


def test_reasoning_first_runtime_keeps_low_salience_details_out_of_entity_candidates() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "summary": "The food items are low-salience event details.",
                "node_vs_detail_notes": [
                    "Eggs with zucchini and peppers should stay as event detail.",
                ],
            },
            {
                "reason": "No durable entity should be planned for the food list.",
                "context_gaps": ["Food details can remain contextual."],
            },
            {
                "reason": "The food detail is too low-salience for a MemoryLog.",
                "context_gaps": ["No memory log action needed."],
            },
            {
                "reason": "No relationship action is required.",
                "context_gaps": ["No resolved relationship endpoints."],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("I ate eggs with zucchini and peppers."),
    )

    assert result.status == IngestionStatus.CANDIDATE_READY
    assert result.entity_candidates == []
    assert result.relationship_plan is not None
    assert result.relationship_plan.actions == []


def test_reasoning_first_runtime_rejects_relationship_actions_with_unknown_endpoints() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "summary": "The source has a relationship but no resolved endpoint.",
                "relationship_notes": ["The endpoint Lorenzo is not resolved."],
            },
            {
                "reason": "No entity action was prepared.",
                "context_gaps": ["No resolved entity endpoint."],
            },
            {
                "reason": "No memory log action is useful without a resolved host.",
                "context_gaps": ["No memory log action needed."],
            },
            {
                "reason": "This plan incorrectly uses a raw endpoint.",
                "actions": [
                    {
                        "local_ref": "CANDIDATE_RELATIONSHIP_001",
                        "goal": "Represent a brother relationship.",
                        "from_ref": "OWNER",
                        "to_ref": "Lorenzo",
                        "relationship_intent": "Lorenzo is the user's brother.",
                        "storage_shape": "direct_relationship",
                        "evidence_text": "brother Lorenzo",
                    },
                ],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("My brother Lorenzo lives in Milan."),
    )

    assert result.status == IngestionStatus.VALIDATION_FAILED
    assert result.relationship_candidates == []
    assert result.validation_errors[0].code == "unknown_relationship_endpoint"
    assert len(provider.requests) == 4


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


class FakeSearchService:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def search_hybrid(
        self,
        query: str,
        *,
        limit: int,
        include_history: bool = True,
    ) -> dict[str, Any]:
        self.calls.append({"query": query, "limit": limit})
        assert include_history is True
        return self.result


def _service(provider: QueuedStructuredProvider, pack: GraphContextPack) -> IngestionService:
    runner = AgenticStateRunner(provider=provider)
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    registry.register_owner("person:owner")
    if not pack.reference_registry_snapshot:
        for entity in pack.entities:
            registry.register_existing(
                f"uat:{entity.ref}",
                object_kind="node",
                label=entity.entity_type or "Node",
                display_label=entity.display_label,
                aliases=entity.aliases,
            )
        pack = pack.model_copy(
            update={
                "alias_map": registry.backend_alias_map(),
                "reference_registry_snapshot": registry.snapshot(),
            },
            deep=True,
        )
    return IngestionService(
        reasoning_service=AgenticReasoningService(runner),
        planning_service=AgenticPlanningService(runner),
        graph_context_builder=StaticGraphContextBuilder(pack),
        entity_extractors=[EntityExtractor(provider)],
        relationship_extractors=[RelationshipExtractor(provider)],
        resolution_agent=FixedResolutionAgent(
            node_action="update" if pack.entities else "create",
            target_ref=pack.entities[0].ref if pack.entities else None,
        ),
    )


def _matteo_pack() -> GraphContextPack:
    return GraphContextPack(
        source_id="source-1",
        compact_summary="Matteo Mercoldi is known as Merc.",
        known_aliases=[
            GraphContextKnownAliasItem(
                alias="Merc",
                target_ref="NODE_000001",
                label="Matteo Mercoldi",
            ),
        ],
        entities=[
            GraphContextEntityItem(
                ref="NODE_000001",
                display_label="Matteo Mercoldi",
                entity_type="Person",
                compact_summary="Known person with alias Merc.",
                aliases=["Merc"],
            ),
        ],
        relationships=[
            GraphContextRelationshipItem(
                ref="REL_000001",
                from_ref="OWNER",
                to_ref="NODE_000001",
                relationship_type="RELATIONSHIP_WITH",
                relationship_kind="family",
                relationship_detail="brother",
            ),
        ],
        duplicate_hints=[
            GraphContextDuplicateHintItem(
                candidate_text="Merc",
                possible_match_refs=["NODE_000001"],
                reason="Exact alias match.",
                score=0.98,
            ),
        ],
        relationship_context_snippets=[
            GraphContextRelationshipSnippetItem(
                ref="SNIPPET_000001",
                endpoint_refs=["OWNER", "NODE_000001"],
                compact_summary="Prior family wording exists.",
            ),
        ],
    )


def _source(text: str) -> SourceRecordRef:
    return SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text=text,
    )
