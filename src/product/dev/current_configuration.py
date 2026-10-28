"""Assemble the current application AI configuration for local inspection."""

from pathlib import Path
from typing import cast

from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import Msg
from product.application.composition import compose_conversation_memory
from product.application.memory_search import (
    MemorySearchFiltersDTO,
    MemorySearchResultDTO,
    MemorySearchSeedDTO,
    MemorySearchService,
)
from product.application.references import ReferenceContext
from product.application.states.conversation_entry import ConversationEntryRequestDTO
from product.application.states.ingestion import IngestionReasoningState
from product.application.states.memory_query import MemoryQueryRequestDTO
from product.application.states.memory_query.models import MemoryQueryContextPacket
from product.application.tools.conversation_entry import (
    IngestMemoryRequestDTO,
    IngestMemoryResultDTO,
)
from product.application.tools.memory_search import (
    MemorySearchToolResultDTO,
    build_memory_search_tool,
)
from product.application.workflows import (
    ApplicationConfigurationInspectionDTO,
    inspect_configured_state,
    inspect_workflow,
)
from product.application.workflows.memory_ingestion.models import (
    IngestionOwnerIdentityDTO,
    IngestionPreparedContextDTO,
)
from product.application.workflows.memory_ingestion.preparation import IngestionContextPreparer
from product.application.workflows.memory_ingestion.workflow import MemoryIngestionWorkflow
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class EmptyInspectionMemoryBackend:
    """Return empty data while composing the inspector without storage I/O."""

    def semantic_seeds(
        self,
        owner_id: str,
        query: str,
        *,
        filters: MemorySearchFiltersDTO,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        return []

    def deterministic_seeds(
        self,
        owner_id: str,
        filters: MemorySearchFiltersDTO,
        *,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        return []

    def hydrate(
        self,
        owner_id: str,
        seed_backend_ids: list[str],
        *,
        filters: MemorySearchFiltersDTO,
        depth: int,
        limit: int,
    ) -> MemorySearchResultDTO:
        return MemorySearchResultDTO()


def current_application_configuration() -> ApplicationConfigurationInspectionDTO:
    """Build inspection DTOs from the actual state, prompt, toolbox, and workflow objects.

    Dependencies:
        Product composition and state ``build_invocation`` methods provide the
        effective runtime configuration. Empty inspection adapters prevent provider
        and storage calls while retaining the real application classes.
    """
    history_session = AgenticHistorySession(
        [Msg(role="user", content="<current user conversation message>")]
    )
    parent = history_session.start_state(
        "conversation_entry",
        history_session.master_history,
    )
    invocation_context = AgenticToolInvocationContext(
        history_session=history_session,
        parent_state_run_id=parent.state_run_id,
        parent_provider_call_id="inspection_tool_call",
    )
    prompt_service = _prompt_service()
    reference_context = ReferenceContext()
    memory_search_service = MemorySearchService(EmptyInspectionMemoryBackend())
    llm_client = cast(LLMInterfaceCore, object())

    composition = compose_conversation_memory(
        owner_id="inspection_owner",
        llm_client=llm_client,
        history_session=history_session,
        prompt_service=prompt_service,
        memory_search_service=memory_search_service,
        reference_context=reference_context,
        ingest_memory=_pending_ingestion_handler,
    )
    conversation_config = composition.conversation_entry.build_invocation(
        ConversationEntryRequestDTO(user_message="<current user conversation message>")
    )
    query_config = composition.memory_query.build_invocation(
        MemoryQueryRequestDTO(goal="<memory question or retrieval goal>"),
        invocation_context,
        MemoryQueryContextPacket(initial_search=MemorySearchToolResultDTO()),
    )

    search_tool = build_memory_search_tool(
        owner_id="inspection_owner",
        service=memory_search_service,
        reference_context=reference_context,
    )
    owner = IngestionOwnerIdentityDTO(
        backend_id="inspection_owner",
        name="Current",
        surname="Owner",
    )
    owner_context = reference_context.register_owner(
        owner.backend_id,
        name=owner.name,
        surname=owner.surname,
    )
    reasoning_state = IngestionReasoningState(
        llm_client,
        history_session,
        prompt_service,
    )
    prepared = IngestionPreparedContextDTO(
        request=IngestMemoryRequestDTO(guidance="<optional ingestion guidance>"),
        owner=owner_context,
        known_references=reference_context.entries(),
        retrieved_memory=MemorySearchToolResultDTO(),
    )
    reasoning_config = reasoning_state.build_invocation(prepared, invocation_context)
    workflow = MemoryIngestionWorkflow(
        IngestionContextPreparer(
            owner=owner,
            reference_context=reference_context,
            search_tool=search_tool,
        ),
        reasoning_state,
    )

    return ApplicationConfigurationInspectionDTO(
        states=[
            inspect_configured_state(
                state_id=composition.conversation_entry.state_id,
                title="Conversation entry",
                description="Answer the user or invoke an available memory capability.",
                input_model=ConversationEntryRequestDTO,
                configuration=conversation_config,
            ),
            inspect_configured_state(
                state_id=composition.memory_query.state_id,
                title="Memory query",
                description="Retrieve and interpret retained memory for a bounded goal.",
                input_model=MemoryQueryRequestDTO,
                configuration=query_config,
            ),
        ],
        workflows=[
            inspect_workflow(
                workflow,
                {reasoning_state.state_id: reasoning_config},
            )
        ],
    )


def _prompt_service() -> PromptService:
    templates_root = Path(__file__).parents[1] / "prompts" / "templates"
    return PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())


def _pending_ingestion_handler(request: IngestMemoryRequestDTO) -> IngestMemoryResultDTO:
    """Represent the current temporary binding until the workflow tool is connected."""
    return IngestMemoryResultDTO(
        result=f"Memory-ingestion workflow binding is pending: {request.guidance or 'no guidance'}"
    )
