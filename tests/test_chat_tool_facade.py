from __future__ import annotations

from my_digital_brain.ai.schemas import ChatResult, ProviderCallMetadata
from my_digital_brain.chat.enums import ChatResponseStatus, PendingProcessKind
from my_digital_brain.chat.facade import ChatToolRequest
from my_digital_brain.chat.models import PendingProcessContext, PendingProcessRef
from my_digital_brain.chat.tool_facade import (
    LLMGraphContextAnswerGenerator,
    MemoryBackendToolFacade,
)
from my_digital_brain.graph.models import GraphContextPackage, NodeSearchResult
from my_digital_brain.ingestion.contracts import IngestionResult
from my_digital_brain.ingestion.enums import IngestionStatus


class FakeGraphService:
    def __init__(self) -> None:
        self.search_query: str | None = None

    def search_nodes(self, **kwargs: object) -> list[NodeSearchResult]:
        self.search_query = str(kwargs.get("query"))
        if self.search_query == "unknown":
            return []
        return [
            NodeSearchResult(
                label="Person",
                labels=["Person"],
                properties={
                    "id": "person-1",
                    "display_name": "Marco",
                    "description": "University friend.",
                },
            )
        ]

    def get_node(self, node_id: str) -> NodeSearchResult:
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, "display_name": "Marco"},
        )

    def get_context_package(self, node_id: str, **_kwargs: object) -> GraphContextPackage:
        return GraphContextPackage(
            target={
                "alias": "NODE_000001",
                "label": "Person",
                "title": "Marco",
                "emotional_summary": "Warm but distant.",
            },
            current_facts=[{"field": "description", "value": "University friend."}],
            relationships=[
                {
                    "alias": "REL_000001",
                    "type": "KNOWS",
                    "description": "Known since university.",
                }
            ],
            timeline=[
                {
                    "alias": "NODE_000002",
                    "label": "Event",
                    "title": "Graduation dinner",
                    "time": "2015",
                }
            ],
            evidence=[
                {
                    "alias": "SOURCE_000001",
                    "label": "Source",
                    "title": "chat note",
                    "description": "I met Marco at university.",
                    "source_ids": ["source-1"],
                }
            ],
            alias_map={"NODE_000001": node_id},
        )


class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.request = None

    def generate_chat(self, request):
        self.request = request
        return ChatResult(
            content="Generated grounded answer.",
            metadata=ProviderCallMetadata.fake(model="fake-answer-model"),
        )


class FakeIngestionService:
    def __init__(self, status: IngestionStatus = IngestionStatus.WRITE_PLAN_READY) -> None:
        self.status = status
        self.sources = []

    def process_source(self, source):
        self.sources.append(source)
        return IngestionResult(
            source_id=source.source_id,
            status=self.status,
        )


class FakeIncompleteIngestionService:
    def __init__(self) -> None:
        self.sources = []

    def process_source(self, source):
        self.sources.append(source)
        return IngestionResult(
            source_id=source.source_id,
            status=IngestionStatus.WRITE_PLAN_READY,
        )


def test_graph_backed_query_returns_context_answer_and_evidence() -> None:
    graph = FakeGraphService()
    facade = MemoryBackendToolFacade(graph_service=graph)

    result = facade.query_memory_context(_request("Marco"))

    assert result.status == ChatResponseStatus.OK
    assert "Marco" in result.primary_text
    assert result.evidence[0].source_id == "source-1"
    assert result.actions[0].action_type == "open_graph_node"
    assert result.metadata["seed_id"] == "person-1"
    assert result.metadata["context_package"]["target"]["alias"] == "NODE_000001"


def test_graph_backed_query_returns_low_noise_no_match_response() -> None:
    facade = MemoryBackendToolFacade(graph_service=FakeGraphService())

    result = facade.query_memory_context(_request("unknown"))

    assert result.status == ChatResponseStatus.OK
    assert "could not find" in result.primary_text
    assert result.diagnostics[0].code == "no_matching_graph_seed"


def test_correction_proposal_requires_confirmation_when_target_found() -> None:
    facade = MemoryBackendToolFacade(graph_service=FakeGraphService())

    result = facade.propose_memory_correction(_request("Marco is from university."))

    assert result.status == ChatResponseStatus.NEEDS_USER_INPUT
    assert result.actions[0].action_type == "confirm_memory_correction"
    assert result.actions[0].requires_confirmation is True
    assert result.metadata["target_id"] == "person-1"


def test_correction_proposal_creates_pending_context_when_target_is_missing() -> None:
    facade = MemoryBackendToolFacade(graph_service=FakeGraphService())

    result = facade.propose_memory_correction(_request("unknown"))

    assert result.status == ChatResponseStatus.NEEDS_USER_INPUT
    assert result.pending_process is not None
    assert result.pending_process.kind == PendingProcessKind.MEMORY_CORRECTION


def test_llm_answer_generator_uses_provider_neutral_chat_request() -> None:
    provider = FakeLLMProvider()
    generator = LLMGraphContextAnswerGenerator(provider, model="fake-answer-model")

    answer = generator.generate_answer(
        question="Who is Marco?",
        context_package=FakeGraphService().get_context_package("person-1"),
        conversation_id="conversation-1",
    )

    assert answer == "Generated grounded answer."
    assert provider.request.model == "fake-answer-model"
    assert provider.request.context.purpose == "memory_question_answer"


def test_resume_pending_memory_ingestion_uses_current_text_and_refreshes_pipeline() -> None:
    ingestion = FakeIngestionService(status=IngestionStatus.WRITTEN)
    facade = MemoryBackendToolFacade(ingestion_service=ingestion)
    pending = PendingProcessContext(
        process_ref=PendingProcessRef(
            process_id="process-1",
            kind=PendingProcessKind.MEMORY_INGESTION,
            question="Which Marco?",
            metadata={"source_id": "source-original"},
        ),
        context={
            "source_text": "Yesterday I met Marco in Milan.",
            "checkpoint_schema_version": "v1",
            "resume_step": "source_reprocess",
        },
    )

    result = facade.resume_pending_process(
        _request("Marco from university").model_copy(
            update={"pending_process_context": pending},
            deep=True,
        ),
    )

    assert result.status == ChatResponseStatus.ACCEPTED
    assert result.metadata["clear_pending_process"] is True
    assert result.metadata["resume_policy"] == "refresh_context_before_write"
    assert ingestion.sources[0].raw_text == (
        "Yesterday I met Marco in Milan.\n\n"
        "Clarification answer: Marco from university"
    )
    assert ingestion.sources[0].metadata["original_source_id"] == "source-original"


def test_missing_ingestion_service_returns_failure_not_placeholder_success() -> None:
    facade = MemoryBackendToolFacade()

    result = facade.start_memory_ingestion(_request("Remember this."))

    assert result.status == ChatResponseStatus.FAILED
    assert "not configured" in result.primary_text
    assert result.diagnostics[0].code == "missing_backend_service"


def test_incomplete_ingestion_result_returns_safe_failure() -> None:
    facade = MemoryBackendToolFacade(
        ingestion_service=FakeIncompleteIngestionService(),
    )

    result = facade.start_memory_ingestion(_request("Remember this."))

    assert result.status == ChatResponseStatus.FAILED
    assert "could not store" in result.primary_text
    assert result.diagnostics[0].code == "ingestion_not_written"


def _request(text: str) -> ChatToolRequest:
    return ChatToolRequest(
        session_id="session-1",
        channel="web",
        conversation_id="conversation-1",
        owner_id="owner-1",
        text=text,
    )
