from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError

from my_digital_brain.agentic import AgenticStateRunner, AgenticToolExecutionContext
from my_digital_brain.ai.schemas import (
    AIRequestContext,
    ChatRequest,
    ChatResult,
    ModelRoute,
    ProviderCallMetadata,
    StructuredGenerationRequest,
    StructuredGenerationResult,
)
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.ingestion.agentic_planner import AgenticIngestionPlanner
from my_digital_brain.ingestion.ai_services import LLMIngestionPlanner, LLMMentionScanner
from my_digital_brain.ingestion.context_retriever import GraphIngestionContextRetriever
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateEntityDraftBatch,
    CandidateOutput,
    ExtractionPlanDraft,
    ExtractionTask,
    IngestionContextPackage,
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
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.extractors import EntityExtractor, PerceptionExtractor
from my_digital_brain.ingestion.prompt_builders import (
    INGESTION_ENTITY_EXTRACTION_TASK,
    INGESTION_MENTION_SCAN_TASK,
    INGESTION_PLANNING_TASK,
    IngestionPromptBuilder,
)
from my_digital_brain.ingestion.service import IngestionService


def test_llm_mention_scanner_uses_structured_provider_and_router() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "mentions": [{"kind": "person", "text": "Marco"}],
            },
        ],
    )
    router = RecordingRouter()

    scan = LLMMentionScanner(provider, router=router).scan(_source())

    assert scan.mentions[0].kind == MentionKind.PERSON
    assert scan.source_id == "source-1"
    assert router.calls[0][0] == INGESTION_MENTION_SCAN_TASK
    assert provider.requests[0].output_schema.__name__ == "MentionScanDraft"
    assert provider.requests[0].context.source_id == "source-1"


@pytest.mark.parametrize(
    "mode",
    [
        ExtractionExecutionMode.SIMPLE_SINGLE_PASS,
        ExtractionExecutionMode.FOCUSED_EXTRACTION,
        ExtractionExecutionMode.NEEDS_CONTEXT_EXPANSION,
        ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST,
    ],
)
def test_llm_planner_accepts_locked_execution_modes(mode: ExtractionExecutionMode) -> None:
    payload: dict[str, Any] = {
        "execution_mode": mode,
    }
    if mode in {
        ExtractionExecutionMode.SIMPLE_SINGLE_PASS,
        ExtractionExecutionMode.FOCUSED_EXTRACTION,
    }:
        payload["tasks"] = [{"task_type": "person", "evidence_text": "Marco"}]
    else:
        payload["tasks"] = []
    if mode == ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST:
        payload["clarification"] = {
            "question": "Which Marco?",
            "reason": "Multiple existing people match.",
        }
    if mode == ExtractionExecutionMode.NEEDS_CONTEXT_EXPANSION:
        payload["context_gaps"] = ["Need more graph context for Marco."]
    provider = QueuedStructuredProvider([payload])
    router = RecordingRouter()

    plan = LLMIngestionPlanner(provider, router=router).plan(
        _source(),
        _empty_scan(),
        IngestionContextPackage(source_id="source-1"),
    )

    assert plan.execution_mode == mode
    assert plan.source_id == "source-1"
    assert router.calls[0][0] == INGESTION_PLANNING_TASK


def test_llm_planner_rejects_extraction_mode_without_tasks() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "execution_mode": "focused_extraction",
                "tasks": [],
            },
        ],
    )

    with pytest.raises(ValidationError, match="at least one extraction task"):
        LLMIngestionPlanner(provider).plan(
            _source(),
            _empty_scan(),
            IngestionContextPackage(source_id="source-1"),
        )


def test_llm_planner_rejects_aliases_not_present_in_context() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "person", "target_ref": "NODE_999"}],
            },
        ],
    )
    context = IngestionContextPackage(
        source_id="source-1",
        aliases={"NODE_001": new_uuid()},
    )

    with pytest.raises(IngestionValidationError, match="not present in compact context"):
        LLMIngestionPlanner(provider).plan(_source(), _empty_scan(), context)


def test_llm_planner_rejects_unsupported_task_types() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "relationship_link"}],
            },
        ],
    )

    with pytest.raises(ValidationError, match="relationship_link"):
        LLMIngestionPlanner(provider).plan(
            _source(),
            _empty_scan(),
            IngestionContextPackage(source_id="source-1"),
        )


def test_agentic_ingestion_planner_returns_structured_plan_without_submit_tool() -> None:
    provider = QueuedToolCallingProvider(
        [{"content": "Ready for structured plan."}],
        structured_payloads=[
            {
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "person", "evidence_text": "Marco"}],
            },
        ],
    )
    planner = AgenticIngestionPlanner(AgenticStateRunner(provider=provider))

    plan = planner.plan(
        _source(),
        _empty_scan(),
        IngestionContextPackage(source_id="source-1"),
    )

    assert plan.tasks[0].task_type == ExtractionTaskType.PERSON
    assert provider.requests[0]["tool_names"] == [
        "request_contradiction_review",
        "request_graph_context_expansion",
    ]
    assert plan.source_id == "source-1"
    assert provider.structured_requests[0].output_schema.__name__ == "ExtractionPlanDraft"
    assert provider.structured_requests[0].max_tokens == 2000


def test_agentic_ingestion_planner_preserves_support_tool_outputs_for_structured_plan() -> None:
    provider = QueuedToolCallingProvider(
        [
            {
                "content": "Expanded context.",
                "tool": "request_graph_context_expansion",
                "arguments": {"query": "Marco", "limit": 5},
            },
        ],
        structured_payloads=[
            {
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "person", "evidence_text": "Marco"}],
            },
        ],
    )
    execution_contexts: list[AgenticToolExecutionContext] = []

    def context_factory(source: SourceRecordRef) -> AgenticToolExecutionContext:
        context = AgenticToolExecutionContext(
            graph_service=FakeGraphService([]),
            metadata={"source_id": source.source_id},
        )
        execution_contexts.append(context)
        return context

    plan = AgenticIngestionPlanner(
        AgenticStateRunner(provider=provider),
        execution_context_factory=context_factory,
    ).plan(_source(), _empty_scan(), IngestionContextPackage(source_id="source-1"))

    assert plan.source_id == "source-1"
    assert plan.tasks[0].task_type == ExtractionTaskType.PERSON
    assert execution_contexts[0].tool_events[0].tool_name == (
        "request_graph_context_expansion"
    )
    structured_context = provider.structured_requests[0].input_message["context"]
    assert structured_context["prior_tool_outputs"][0]["tool_name"] == (
        "request_graph_context_expansion"
    )


def test_agentic_ingestion_planner_reports_invalid_structured_plan() -> None:
    provider = QueuedToolCallingProvider(
        [{"content": "Ready for structured plan."}],
        structured_payloads=[
            {
                "source_id": "wrong-source",
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "person"}],
            },
        ],
    )

    with pytest.raises(IngestionValidationError, match="source_id"):
        AgenticIngestionPlanner(AgenticStateRunner(provider=provider)).plan(
            _source(),
            _empty_scan(),
            IngestionContextPackage(source_id="source-1"),
        )


def test_agentic_ingestion_planner_can_detour_through_contradiction_review() -> None:
    provider = QueuedToolCallingProvider(
        [
            {
                "content": "Need contradiction review.",
                "tool": "request_contradiction_review",
                "arguments": {
                    "agent_doubt": "The event place conflicts with retrieved context.",
                    "proposed_write_ref": "WRITE_000001",
                    "affected_entity_refs": ["NODE_000001"],
                    "source_refs": ["source-1"],
                },
            },
            {"content": "Treat this as a temporal nuance and continue."},
            {"content": "Ready for structured plan."},
        ],
        structured_payloads=[
            {
                "judge_request_id": "judge-1",
                "intent": "emit_verdict",
                "decision": "nuance",
                "severity": "low",
                "reason": "Treat this as a temporal nuance and continue.",
                "graph_action": "allow_write",
                "inspected_context_refs": ["NODE_000001"],
            },
            {
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "event", "evidence_text": "met Marco"}],
            },
        ],
    )
    context = IngestionContextPackage(
        source_id="source-1",
        aliases={"NODE_000001": new_uuid()},
    )

    plan = AgenticIngestionPlanner(
        AgenticStateRunner(provider=provider),
        max_planning_rounds=2,
    ).plan(_source(), _empty_scan(), context)

    assert plan.tasks[0].task_type == ExtractionTaskType.EVENT
    assert len(provider.requests) == 3
    assert provider.requests[1]["tool_names"] == [
        "get_change_records",
        "get_neighborhood_view",
        "get_node_detail",
        "get_relationship_state_history",
        "get_target_evidence",
    ]
    assert provider.requests[2]["tool_names"] == [
        "request_contradiction_review",
        "request_graph_context_expansion",
    ]
    assert provider.structured_requests[0].output_schema.__name__ == (
        "ContradictionJudgeResultContext"
    )
    assert provider.structured_requests[1].output_schema is ExtractionPlanDraft


def test_graph_context_retriever_returns_low_noise_alias_packages() -> None:
    person_id = new_uuid()
    service = FakeGraphService(
        [
            NodeSearchResult(
                label="Person",
                labels=["Person"],
                properties={
                    "id": person_id,
                    "display_name": "Marco Rossi",
                    "description": "University friend.",
                    "emotional_summary": "Warm but distant.",
                    "metadata": {"debug": "do not expose"},
                },
            ),
        ],
    )
    mention_scan = _empty_scan()
    mention_scan.mentions.append(
        mention_scan.mentions[0].model_copy(update={"kind": "person", "text": "Marco"})
    )

    context = GraphIngestionContextRetriever(service).retrieve(_source(), mention_scan)

    assert context.entities[0]["alias"] == "NODE_000001"
    assert context.entities[0]["title"] == "Marco Rossi"
    assert context.entities[0]["emotional_summary"] == "Warm but distant."
    assert "metadata" not in context.entities[0]
    assert context.aliases == {"NODE_000001": person_id}


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
    task = ExtractionTask(task_type=ExtractionTaskType.PERSON, source_refs=["source-1"])

    candidates = extractor.extract(_source(), task, IngestionContextPackage(source_id="source-1"))

    assert extractor.supports(task) is True
    assert isinstance(candidates[0], CandidateEntity)
    assert candidates[0].source_refs == ["source-1"]
    assert candidates[0].evidence_refs[0].source_id == "source-1"
    assert candidates[0].evidence_refs[0].evidence_text == "Marco"
    assert candidates[0].typed_properties == {"nickname": "Marco"}
    assert not PerceptionExtractor(provider).supports(task)
    assert provider.requests[0].output_schema is CandidateEntityDraftBatch
    assert provider.requests[0].context.purpose == INGESTION_ENTITY_EXTRACTION_TASK


def test_pipeline_runs_with_ai_services_and_fake_provider() -> None:
    provider = QueuedStructuredProvider(
        [
            {
                "mentions": [{"kind": "person", "text": "Marco"}],
            },
            {
                "execution_mode": "focused_extraction",
                "tasks": [{"task_type": "person", "evidence_text": "Marco"}],
            },
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
    service = IngestionService(
        scanner=LLMMentionScanner(provider),
        context_retriever=StaticContextRetriever(),
        planner=LLMIngestionPlanner(provider),
        extractors=[EntityExtractor(provider)],
    )

    result = service.process_source(_source())

    assert result.status == IngestionStatus.CANDIDATE_READY
    assert result.candidate_graph is not None
    assert result.candidate_graph.candidate_entities[0].display_name == "Marco"
    assert len(provider.requests) == 3


def test_prompt_builder_excludes_noisy_source_metadata() -> None:
    source = _source(metadata={"debug": "noisy", "provider_payload": {"nested": True}})

    payload = IngestionPromptBuilder().mention_scan_input(source)

    assert "metadata" not in payload["source"]
    assert payload["source"]["raw_text"] == source.raw_text


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


class QueuedToolCallingProvider:
    provider_name = "fake"

    def __init__(
        self,
        steps: Sequence[dict[str, Any]],
        *,
        structured_payloads: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        self.steps = list(steps)
        self.requests: list[dict[str, Any]] = []
        self.structured_payloads = list(structured_payloads or [])
        self.structured_requests: list[StructuredGenerationRequest] = []

    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, Any],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        step = self.steps.pop(0)
        self.requests.append(
            {
                "request": request,
                "tool_names": sorted(toolbox.tools_by_name),
                "max_tool_calls": max_tool_calls,
            }
        )
        tool_name = step.get("tool")
        if isinstance(tool_name, str):
            tools_mapping[tool_name](**dict(step.get("arguments") or {}))
        for tool_call in step.get("tool_calls") or []:
            tools_mapping[tool_call["tool"]](**dict(tool_call.get("arguments") or {}))
        return ChatResult(
            content=str(step.get("content") or ""),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )

    def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredGenerationResult:
        self.structured_requests.append(request)
        payload = self.structured_payloads.pop(0)
        parsed = request.output_schema.model_validate(payload)
        return StructuredGenerationResult(
            parsed=parsed,
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


class RecordingRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, AIRequestContext | None]] = []

    def route(
        self,
        task: str,
        context: AIRequestContext | None = None,
    ) -> ModelRoute:
        self.calls.append((task, context))
        return ModelRoute(task=task, provider="fake", model=f"{task}-model")


class FakeGraphService:
    def __init__(self, nodes: list[NodeSearchResult]) -> None:
        self.nodes = nodes
        self.calls: list[dict[str, Any]] = []

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        limit: int = 25,
        **_: Any,
    ) -> list[NodeSearchResult]:
        self.calls.append({"label": label, "query": query, "limit": limit})
        return [node for node in self.nodes if label is None or node.label == label][:limit]


class StaticContextRetriever:
    def retrieve(
        self,
        source: SourceRecordRef,
        mention_scan,
    ) -> IngestionContextPackage:
        return IngestionContextPackage(source_id=source.source_id)


def _source(metadata: dict[str, Any] | None = None) -> SourceRecordRef:
    return SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Marco in Milan and felt happy.",
        metadata=metadata or {},
    )


def _empty_scan():
    from my_digital_brain.ingestion.contracts import Mention, MentionScan

    return MentionScan(
        source_id="source-1",
        mentions=[Mention(kind=MentionKind.PERSON, text="placeholder")],
    )
