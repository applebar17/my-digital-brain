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
from product.application.states.ingestion import (
    IngestionReasoningResultDTO,
    IngestionReasoningState,
    MemoryContextWriteInputDTO,
    MemoryContextWriteState,
    NodeCandidateSetDTO,
    NodeCandidateState,
    NodeCandidateStateInputDTO,
)
from product.application.states.ingestion.node_candidate import PersonCandidateDTO
from product.application.states.ingestion.node_resolution import (
    NodeBatchPolicyDTO,
    NodeCandidateBatchPlanner,
    NodeResolutionBatchPreparer,
    NodeResolutionStateInputDTO,
    NodeResolutionWriteState,
)
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
from product.graph import (
    CreatePerceptionPersistenceDTO,
    GraphIdentityLookupService,
    GraphMemoryRepository,
    GraphMemoryService,
    GraphNodeRepository,
    GraphNodeService,
    MemoryLogWriteDTO,
    NodeCreate,
    NodeType,
    StoredMemoryLogDTO,
    StoredNodeDTO,
    StoredPerceptionDTO,
)
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


class EmptyInspectionGraphRepository(GraphNodeRepository):
    """Expose real graph contracts to inspection without storage I/O."""

    def search_nodes(
        self,
        owner_id: str,
        node_type: NodeType,
        terms: list[str],
        *,
        limit: int,
    ) -> list[StoredNodeDTO]:
        return []

    def get_node(
        self,
        owner_id: str,
        backend_id: str,
        node_type: NodeType,
    ) -> StoredNodeDTO:
        raise ValueError("Inspection does not load graph nodes.")

    def create_node(self, owner_id: str, node: NodeCreate) -> StoredNodeDTO:
        raise ValueError("Inspection does not write graph nodes.")


class EmptyInspectionMemoryRepository(GraphMemoryRepository):
    """Expose memory persistence contracts without storage I/O."""

    def create_memory_log(
        self,
        owner_id: str,
        memory_log: MemoryLogWriteDTO,
    ) -> StoredMemoryLogDTO:
        raise ValueError("Inspection does not write memory logs.")

    def create_perception(
        self,
        owner_id: str,
        request: CreatePerceptionPersistenceDTO,
    ) -> StoredPerceptionDTO:
        raise ValueError("Inspection does not write perceptions.")

    def update_node(
        self,
        owner_id: str,
        backend_id: str,
        node: NodeCreate,
    ) -> StoredNodeDTO:
        raise ValueError("Inspection does not write graph nodes.")


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
    candidate_state = NodeCandidateState(
        llm_client,
        history_session,
        prompt_service,
    )
    candidate_input = NodeCandidateStateInputDTO(
        reasoning=IngestionReasoningResultDTO(
            summary="<ingestion reasoning summary>",
            clarification_points=[],
            entity_observations=[],
            alias_observations=[],
            relationship_observations=[],
            episodic_details=[],
        ),
        owner=owner_context,
        known_references=reference_context.entries(),
    )
    candidate_config = candidate_state.build_invocation(
        candidate_input,
        invocation_context,
    )
    graph_repository = EmptyInspectionGraphRepository()
    graph_service = GraphNodeService(graph_repository)
    batch_planner = NodeCandidateBatchPlanner(NodeBatchPolicyDTO())
    resolution_preparer = NodeResolutionBatchPreparer(
        owner_id=owner.backend_id,
        identity_lookup=GraphIdentityLookupService(graph_repository),
        reference_context=reference_context,
    )
    resolution_state = NodeResolutionWriteState(
        llm_client,
        history_session,
        prompt_service,
        owner_id=owner.backend_id,
        graph_service=graph_service,
        reference_context=reference_context,
    )
    inspection_candidates = NodeCandidateSetDTO(
        candidates=[
            PersonCandidateDTO(
                node_type=NodeType.PERSON,
                description="<candidate description>",
                aliases=[],
                identity_gaps=[],
                display_name="<candidate person>",
                given_name=None,
                surname=None,
                known_since=None,
            )
        ]
    )
    inspection_batch = batch_planner.plan(inspection_candidates, reference_context)[0]
    resolution_input = resolution_preparer.prepare(inspection_batch, owner_context)
    resolution_config = resolution_state.build_invocation(
        resolution_input,
        invocation_context,
    )
    memory_context_state = MemoryContextWriteState(
        llm_client,
        history_session,
        prompt_service,
        owner_id=owner.backend_id,
        graph_memory_service=GraphMemoryService(EmptyInspectionMemoryRepository()),
        reference_context=reference_context,
    )
    memory_context_config = memory_context_state.build_invocation(
        MemoryContextWriteInputDTO(
            reasoning=candidate_input.reasoning,
            node_resolution_results=[],
            owner=owner_context,
            references=reference_context.entries(),
        ),
        invocation_context,
    )
    workflow = MemoryIngestionWorkflow(
        IngestionContextPreparer(
            owner=owner,
            reference_context=reference_context,
            search_tool=search_tool,
        ),
        reasoning_state,
        candidate_state,
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
            inspect_configured_state(
                state_id=resolution_state.state_id,
                title="Node resolution and write",
                description=(
                    "Resolve one configured candidate batch through typed create/update "
                    "and optional clarification tools."
                ),
                input_model=NodeResolutionStateInputDTO,
                configuration=resolution_config,
            ),
            inspect_configured_state(
                state_id=memory_context_state.state_id,
                title="Memory and perception write",
                description=(
                    "Create concise memory atoms and subjective perceptions through "
                    "typed deterministic tools."
                ),
                input_model=MemoryContextWriteInputDTO,
                configuration=memory_context_config,
            ),
        ],
        workflows=[
            inspect_workflow(
                workflow,
                {
                    reasoning_state.state_id: reasoning_config,
                    candidate_state.state_id: candidate_config,
                    resolution_state.state_id: resolution_config,
                },
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
