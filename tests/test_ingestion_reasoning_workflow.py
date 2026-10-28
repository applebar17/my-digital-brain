"""Functional preparation and reasoning for the first memory-ingestion slice."""

from copy import deepcopy
from pathlib import Path
from typing import Any

from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext, RegisteredTool
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.references import (
    ReferenceContext,
    ReferenceObjectKind,
    ReferenceResolutionStatus,
)
from product.application.states.ingestion import (
    IngestionReasoningResultDTO,
    IngestionReasoningState,
)
from product.application.tools.memory_search import (
    MemorySearchObjectDTO,
    MemorySearchToolInputDTO,
    MemorySearchToolResultDTO,
)
from product.application.workflows import inspect_workflow
from product.application.workflows.memory_ingestion.models import (
    IngestionOwnerIdentityDTO,
    IngestMemoryRequestDTO,
)
from product.application.workflows.memory_ingestion.preparation import IngestionContextPreparer
from product.application.workflows.memory_ingestion.workflow import MemoryIngestionWorkflow
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class IngestionReasoningClient:
    """Return one structured interpretation while recording the state request."""

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []
        self.mapping_names: list[str] = []

    def handle_params(
        self,
        *,
        system_prompt: str,
        chat_messages: list[Msg],
        **_kwargs: Any,
    ) -> ChatRequest:
        return ChatRequest(
            model="test-model",
            messages=[Msg(role="system", content=system_prompt), *deepcopy(chat_messages)],
        )

    def call(self, request: ChatRequest, mapping: dict[str, Any]) -> ChatResponse:
        self.requests.append(deepcopy(request))
        self.mapping_names = sorted(mapping)
        return ChatResponse(
            message=Msg(
                role="assistant",
                content={
                    "summary": "The user describes a Rome trip with an unclear companion.",
                    "clarification_points": [
                        "'With Jacopo' is unclear because two known people share that name; "
                        "identity affects later person resolution."
                    ],
                    "entity_observations": ["Rome is a place mentioned in the trip."],
                    "alias_observations": [],
                    "relationship_observations": [
                        "Travelling together indicates trip involvement, not a durable "
                        "relationship."
                    ],
                    "episodic_details": ["The trip happened last week."],
                },
            )
        )


def _prompt_service() -> PromptService:
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    return PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())


def test_workflow_inherits_conversation_and_prioritizes_clarification_points() -> None:
    reference_context = ReferenceContext()
    search_queries: list[str] = []

    def search(request: MemorySearchToolInputDTO) -> MemorySearchToolResultDTO:
        search_queries.append(request.semantic_query or "")
        jacopo = reference_context.register_existing(
            "person-jacopo-backend",
            object_kind=ReferenceObjectKind.NODE,
            label="Person",
            display_name="Jacopo Brutti",
            summary="A known person named Jacopo.",
        )
        return MemorySearchToolResultDTO(
            seed_refs=[jacopo.ref],
            objects=[
                MemorySearchObjectDTO(
                    **jacopo.model_dump(),
                    temporal_summary=None,
                )
            ],
        )

    search_tool = RegisteredTool(
        definition=ToolDefinitionDTO[MemorySearchToolInputDTO](
            name="search_memory",
            description="Retrieve bounded memory context.",
            input_model=MemorySearchToolInputDTO,
        ),
        handler=search,
    )
    history_session = AgenticHistorySession()
    parent = history_session.start_state(
        "conversation_entry",
        [
            Msg(role="user", content="I went to Rome last week."),
            Msg(role="assistant", content="Who were you with?"),
            Msg(role="user", content="With Jacopo."),
        ],
    )
    invocation_context = AgenticToolInvocationContext(
        history_session=history_session,
        parent_state_run_id=parent.state_run_id,
        parent_provider_call_id="ingest-call-001",
    )
    client = IngestionReasoningClient()
    reasoning_state = IngestionReasoningState(
        client,  # type: ignore[arg-type]
        history_session,
        _prompt_service(),
    )
    workflow = MemoryIngestionWorkflow(
        IngestionContextPreparer(
            owner=IngestionOwnerIdentityDTO(
                backend_id="owner-backend-id",
                name="Mario",
                surname="Rossi",
            ),
            reference_context=reference_context,
            search_tool=search_tool,
        ),
        reasoning_state,
    )

    result = workflow.run_initial_slice(
        IngestMemoryRequestDTO(guidance="Retain the trip memory."),
        invocation_context,
    )

    assert isinstance(result, IngestionReasoningResultDTO)
    assert result.clarification_points == [
        "'With Jacopo' is unclear because two known people share that name; "
        "identity affects later person resolution."
    ]
    assert search_queries == [
        "user: I went to Rome last week.\n"
        "assistant: Who were you with?\n"
        "user: With Jacopo."
    ]
    sent = client.requests[0]
    assert [message.as_text() for message in sent.messages[1:-1]] == [
        "I went to Rome last week.",
        "Who were you with?",
        "With Jacopo.",
    ]
    assert "Mario Rossi" in sent.messages[0].as_text()
    assert "Jacopo Brutti" in sent.messages[0].as_text()
    assert client.mapping_names == []
    assert reference_context.entry_for("mario_rossi").resolution_status == (
        ReferenceResolutionStatus.EXISTING
    )

    inspected = inspect_workflow(workflow)
    assert [step.kind for step in inspected.steps] == ["deterministic", "agentic"]
    assert inspected.steps[1].input_model.name == "IngestionPreparedContextDTO"
    assert inspected.steps[1].output_model.name == "IngestionReasoningResultDTO"
