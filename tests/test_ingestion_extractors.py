from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError

from my_digital_brain.ai.schemas import ProviderCallMetadata
from my_digital_brain.ai.session import LLMSessionCompleted, LLMSessionRequest
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateEntityDraftBatch,
    CandidateRelationshipDraftBatch,
    ExtractionTask,
    IngestionContextPackage,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import ExtractionTaskType, SourceChannel, SourceType
from my_digital_brain.ingestion.extractors import (
    EntityExtractor,
    PerceptionExtractor,
    RelationshipExtractor,
)
from my_digital_brain.ingestion.prompt_builders import (
    INGESTION_ENTITY_EXTRACTION_TASK,
    INGESTION_RELATIONSHIP_EXTRACTION_TASK,
    IngestionPromptBuilder,
)


def test_focused_entity_extractor_returns_only_entity_candidates() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "Marco",
                        "evidence": [
                            {
                                "evidence_text": "Marco",
                                "span_start": 6,
                                "span_end": 11,
                            },
                        ],
                        "property_suggestions": [
                            {
                                "key": "nickname",
                                "value_text": "Marco",
                                "value_kind": "text",
                            },
                        ],
                    },
                ],
            },
        ],
    )
    extractor = EntityExtractor(provider)
    task = ExtractionTask(
        task_type=ExtractionTaskType.PERSON,
        target_ref="CANDIDATE_PERSON_042",
        source_refs=["source-1"],
    )

    source = _source()
    candidates = extractor.extract(source, task, IngestionContextPackage(source_id="source-1"))

    assert extractor.supports(task) is True
    assert isinstance(candidates[0], CandidateEntity)
    assert candidates[0].source_refs == ["source-1"]
    assert candidates[0].local_ref == "CANDIDATE_PERSON_042"
    assert candidates[0].metadata["model_output_local_ref"] == "CANDIDATE_PERSON_001"
    assert candidates[0].metadata["local_ref_enforced_from_task"] == ("CANDIDATE_PERSON_042")
    assert candidates[0].evidence_refs[0].source_id == "source-1"
    assert candidates[0].evidence_refs[0].evidence_text == "Marco"
    assert candidates[0].typed_properties == {"nickname": "Marco"}
    assert not PerceptionExtractor(provider).supports(task)
    assert provider.requests[0].output_schema is CandidateEntityDraftBatch
    assert provider.requests[0].context.purpose == INGESTION_ENTITY_EXTRACTION_TASK
    assert provider.requests[0].messages[-1].role == "user"
    assert len(provider.requests[0].messages) == 2
    assert provider.requests[0].messages[0].role == "user"
    assert provider.requests[0].messages[0].content == source.raw_text
    assert provider.requests[0].messages[-1].role == "user"
    assert "Ingest this planning target/action" in (provider.requests[0].messages[-1].content or "")
    assert "raw_text" not in (provider.requests[0].messages[-1].content or "")


def test_focused_entity_extractor_batches_planned_targets() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "candidates": [
                    {
                        "local_ref": "MODEL_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "Marco",
                    },
                    {
                        "local_ref": "CANDIDATE_PERSON_002",
                        "entity_type": "Person",
                        "display_name": "Luca",
                    },
                ],
            },
        ],
    )
    extractor = EntityExtractor(provider)
    tasks = [
        ExtractionTask(
            task_type=ExtractionTaskType.PERSON,
            target_ref="CANDIDATE_PERSON_001",
            source_refs=["source-1"],
        ),
        ExtractionTask(
            task_type=ExtractionTaskType.PERSON,
            target_ref="CANDIDATE_PERSON_002",
            source_refs=["source-1"],
        ),
    ]

    candidates = extractor.extract_batch(
        _source(),
        tasks,
        IngestionContextPackage(source_id="source-1"),
    )

    assert len(provider.requests) == 1
    assert [candidate.local_ref for candidate in candidates] == [
        "CANDIDATE_PERSON_001",
        "CANDIDATE_PERSON_002",
    ]
    assert candidates[0].metadata["model_output_local_ref"] == "MODEL_PERSON_001"
    assert provider.requests[0].context.metadata["batch_size"] == 2
    assert provider.requests[0].messages[0].content == _source().raw_text
    final_message = provider.requests[0].messages[-1].content or ""
    assert "Ingest these planning targets/actions" in final_message
    assert "CANDIDATE_PERSON_001" in final_message
    assert "CANDIDATE_PERSON_002" in final_message
    assert "raw_text" not in final_message


def test_focused_extractors_reject_freeform_labels_and_relationship_types() -> None:
    with pytest.raises(ValidationError, match="GameEvent"):
        CandidateEntityDraftBatch.model_validate(
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_EVENT_001",
                        "entity_type": "GameEvent",
                    }
                ],
            },
        )
    with pytest.raises(ValidationError, match="romantic_partner"):
        CandidateRelationshipDraftBatch.model_validate(
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_REL_001",
                        "relationship_type": "romantic_partner",
                        "from_ref": "CANDIDATE_PERSON_001",
                        "to_ref": "CANDIDATE_PERSON_002",
                    }
                ],
            },
        )


def test_focused_relationship_extractor_preserves_social_kind_and_detail() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_REL_001",
                        "relationship_type": "RELATIONSHIP_WITH",
                        "from_ref": "CANDIDATE_PERSON_001",
                        "to_ref": "CANDIDATE_PERSON_002",
                        "relationship_kind": "partner",
                        "relationship_detail": "girlfriend",
                    },
                ],
            },
        ],
    )

    relationship = RelationshipExtractor(provider).extract(
        _source(),
        ExtractionTask(task_type=ExtractionTaskType.RELATIONSHIP, source_refs=["source-1"]),
        IngestionContextPackage(source_id="source-1"),
    )[0]

    assert relationship.relationship_type == "RELATIONSHIP_WITH"
    assert relationship.relationship_kind == "partner"
    assert relationship.relationship_detail == "girlfriend"
    assert provider.requests[0].context.purpose == INGESTION_RELATIONSHIP_EXTRACTION_TASK


def test_prompt_builder_excludes_source_text_from_ingestion_payload() -> None:
    source = _source(metadata={"debug": "noisy", "provider_payload": {"nested": True}})

    payload = IngestionPromptBuilder().extraction_input(
        source,
        ExtractionTask(task_type=ExtractionTaskType.PERSON, source_refs=["source-1"]),
        IngestionContextPackage(source_id="source-1"),
    )

    assert "source" not in payload
    assert "raw_text" not in str(payload)


def test_extraction_prompt_preserves_ambiguous_candidates_for_resolution() -> None:
    prompt = IngestionPromptBuilder.extractor_system_prompt

    assert "Preserve the best supported ambiguous name" in prompt
    assert "ask for clarification before proposing a node action" in prompt
    assert "apply the clarified value to the structured candidate fields" in prompt
    assert "only when the user explicitly asks not to save or to defer" in prompt


def test_focused_extractor_keeps_clarification_history_before_ingestion_instruction() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "candidates": [
                    {
                        "local_ref": "CANDIDATE_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "Marco",
                    },
                ],
            },
        ],
    )
    source = _source(
        metadata={
            "model_facing_history": [
                {"role": "assistant", "content": "Clarification needed: Which Marco?"},
                {"role": "user", "content": "Clarification answer: Marco from Milan."},
            ],
        },
    )

    EntityExtractor(provider).extract(
        source,
        ExtractionTask(
            task_type=ExtractionTaskType.PERSON,
            target_ref="CANDIDATE_PERSON_001",
            source_refs=["source-1"],
        ),
        IngestionContextPackage(source_id="source-1"),
    )

    assert [message.role for message in provider.requests[0].messages] == [
        "user",
        "assistant",
        "user",
        "user",
    ]
    assert provider.requests[0].messages[0].content == "I met Marco in Milan and felt happy."
    assert provider.requests[0].messages[1].content == ("Clarification needed: Which Marco?")
    assert provider.requests[0].messages[2].content == ("Clarification answer: Marco from Milan.")
    assert "Ingest this planning target/action" in (provider.requests[0].messages[3].content or "")


class QueuedStructuredProvider:
    provider_name = "fake"

    def __init__(self, payloads: Sequence[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[LLMSessionRequest] = []

    def run_session(
        self,
        request: LLMSessionRequest,
    ) -> LLMSessionCompleted:
        self.requests.append(request)
        payload = self.payloads.pop(0)
        assert request.output_schema is not None
        parsed = request.output_schema.model_validate(payload)
        return LLMSessionCompleted(
            session_id=request.session_id or "test-session",
            messages=request.messages,
            content=parsed.model_dump_json(),
            parsed=parsed,
            metadata=ProviderCallMetadata.fake(model=request.model or "fake-model"),
        )


def _source(metadata: dict[str, Any] | None = None) -> SourceRecordRef:
    return SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Marco in Milan and felt happy.",
        metadata=metadata or {},
    )
