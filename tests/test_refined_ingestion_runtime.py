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
    DeterministicResolvedEntityMapBuilder,
    RefinedIngestionService,
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
from my_digital_brain.ingestion.extractors import EntityExtractor


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


def test_refined_runtime_matches_merc_alias_to_existing_entity_before_relationship_planning() -> None:
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
                        "action_ref": "ENTITY_ACTION_001",
                        "goal": "Extract Matteo Mercoldi as one person candidate.",
                        "mention_text": "Matteo Mercoldi",
                        "suggested_entity_type": "Person",
                        "aliases": ["Merc"],
                        "evidence_text": "Merc is Matteo Mercoldi.",
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
                "reason": "No relationship action is needed from this source.",
                "context_gaps": ["No relationship action needed."],
            },
        ],
    )
    result = _service(provider, _matteo_pack()).process_source(
        _source("Merc is Matteo Mercoldi."),
    )

    assert result.status == IngestionStatus.PLANNED
    assert result.reasoning is not None
    assert result.entity_plan is not None
    assert result.resolved_entity_map is not None
    assert result.resolved_entity_map.entries[0].status == (
        ResolvedEntityStatus.MATCHED_EXISTING.value
    )
    assert result.resolved_entity_map.entries[0].graph_alias == "NODE_000001"
    assert result.relationship_plan is not None
    assert provider.requests[0].output_schema.__name__ == "IngestionReasoningCheckpointDraft"
    assert provider.requests[1].output_schema.__name__ == "EntityIngestionPlanDraft"
    assert provider.requests[2].output_schema.__name__ == "CandidateEntityDraftBatch"
    assert provider.requests[3].output_schema.__name__ == "RelationshipIngestionPlanDraft"


def test_refined_runtime_plans_brother_relationship_against_staged_entity_ref() -> None:
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
                        "action_ref": "ENTITY_ACTION_001",
                        "goal": "Extract Lorenzo as a person candidate.",
                        "mention_text": "Lorenzo",
                        "suggested_entity_type": "Person",
                        "evidence_text": "my brother Lorenzo",
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
                "reason": "The resolved entity map provides Lorenzo as a staged ref.",
                "actions": [
                    {
                        "action_ref": "REL_ACTION_001",
                        "goal": "Plan the user-to-Lorenzo brother relationship.",
                        "from_ref": "OWNER",
                        "to_ref": "CANDIDATE_PERSON_001",
                        "relationship_intent": "Lorenzo is the user's brother.",
                        "storage_shape": "direct_relationship",
                        "evidence_text": "my brother Lorenzo",
                    },
                ],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("My brother Lorenzo lives in Milan."),
    )

    assert result.status == IngestionStatus.PLANNED
    assert result.resolved_entity_map is not None
    assert result.resolved_entity_map.relationship_usable_refs == {
        "CANDIDATE_PERSON_001": "CANDIDATE_PERSON_001",
    }
    assert result.relationship_plan is not None
    assert result.relationship_plan.actions[0].to_ref == "CANDIDATE_PERSON_001"
    assert result.relationship_plan.actions[0].relationship_intent == (
        "Lorenzo is the user's brother."
    )


def test_refined_runtime_allows_relationship_planning_to_emit_missing_entity_required() -> None:
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
                "reason": "The brother relationship is blocked by a missing endpoint.",
                "missing_entities": [
                    {
                        "missing_ref": "MISSING_ENTITY_001",
                        "reason": "The brother endpoint is required.",
                        "mention_text": "my brother",
                        "suggested_entity_type": "Person",
                        "needed_for_relationship_ref": "REL_ACTION_001",
                        "relationship_goal": "Represent the user's brother relationship.",
                        "relationship_endpoint_role": "to",
                        "evidence_text": "my brother",
                        "entity_planning_guidance": "Plan one person endpoint for the brother.",
                        "relationship_resume_guidance": "Resume REL_ACTION_001 after resolution.",
                    },
                ],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("My brother lives in Milan."),
    )

    assert result.status == IngestionStatus.PLANNED
    assert result.entity_candidates == []
    assert result.resolved_entity_map is not None
    assert result.resolved_entity_map.relationship_usable_refs == {}
    assert result.relationship_plan is not None
    assert result.relationship_plan.missing_entities[0].missing_ref == "MISSING_ENTITY_001"
    assert len(provider.requests) == 3


def test_refined_runtime_keeps_low_salience_details_out_of_entity_candidates() -> None:
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
                "reason": "No relationship action is required.",
                "context_gaps": ["No resolved relationship endpoints."],
            },
        ],
    )

    result = _service(provider, GraphContextPack(source_id="source-1")).process_source(
        _source("I ate eggs with zucchini and peppers."),
    )

    assert result.status == IngestionStatus.PLANNED
    assert result.entity_candidates == []
    assert result.relationship_plan is not None
    assert result.relationship_plan.actions == []


def test_refined_entity_resolver_rejected_entries_are_not_relationship_usable() -> None:
    resolver = DeterministicResolvedEntityMapBuilder()
    resolved = resolver.resolve(
        [
            CandidateEntity(
                local_ref="CANDIDATE_BAD_001",
                entity_type="UnsafeLabel",
                display_name="Unsupported",
                source_refs=["source-1"],
            ),
        ],
        GraphContextPack(source_id="source-1"),
    )

    assert resolved.entries[0].status == ResolvedEntityStatus.REJECTED.value
    assert resolved.entries[0].relationship_ref is None
    assert resolved.relationship_usable_refs == {}


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


def _service(provider: QueuedStructuredProvider, pack: GraphContextPack) -> RefinedIngestionService:
    runner = AgenticStateRunner(provider=provider)
    return RefinedIngestionService(
        reasoning_service=AgenticReasoningService(runner),
        planning_service=AgenticPlanningService(runner),
        graph_context_builder=StaticGraphContextBuilder(pack),
        entity_extractors=[EntityExtractor(provider)],
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
