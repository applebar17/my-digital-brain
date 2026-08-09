from __future__ import annotations

from typing import Any

from my_digital_brain.agentic import AgenticPlanningService, AgenticReasoningService
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime import AgenticRuntime, AgenticStateRunner
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ai.client.settings import genai_settings_from_app_settings
from my_digital_brain.ai.providers import AzureOpenAIProvider, OpenAIProvider
from my_digital_brain.ai.router import StaticModelRouter
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import ChatSessionStore
from my_digital_brain.config import Settings
from my_digital_brain.core.owner_context import OwnerSnapshot
from my_digital_brain.graph.owner import OwnerNodeManager
from my_digital_brain.graph.owner_profile import OwnerProfileReader
from my_digital_brain.ingestion.candidate_context import BoundedCandidateContextHydrator
from my_digital_brain.ingestion.executor import GraphWritePlanExecutor
from my_digital_brain.ingestion.extractors import (
    ClaimExtractor,
    EntityExtractor,
    MetadataPatchExtractor,
    PerceptionExtractor,
    ProfileMemoryExtractor,
    RelationshipContextExtractor,
    RelationshipExtractor,
)
from my_digital_brain.ingestion.graph_context_pack import WholeSourceGraphContextPackBuilder
from my_digital_brain.ingestion.identity_lookup import DeterministicIdentityLookupService
from my_digital_brain.ingestion.resolution_agent import LLMResolutionProposalAgent
from my_digital_brain.ingestion.service import IngestionService
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder
from my_digital_brain.rag import (
    GraphVectorizationService,
    SemanticMemorySearchService,
    VectorRecordStore,
)
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.vector import ChromaVectorStore


def build_chat_runtime(
    *,
    settings: Settings,
    store: ChatSessionStore,
    graph_service: Any | None = None,
) -> ChatRuntime:
    """Build the production agentic chat runtime from app settings."""

    provider = build_ai_provider(settings)

    router = StaticModelRouter(
        settings=genai_settings_from_app_settings(settings),
        provider=settings.normalized_llm_provider,
    )
    history_service = AgenticHistoryService()
    state_runner = AgenticStateRunner(
        provider=provider,
        model_router=router,
        history_service=history_service,
    )
    agentic_runtime = AgenticRuntime(state_runner)
    semantic_search_service = (
        build_semantic_search_service(
            settings=settings,
            provider=provider,
            graph_service=graph_service,
            router=router,
        )
        if graph_service is not None
        else None
    )
    owner_manager = (
        OwnerNodeManager(graph_service.repository, settings)
        if graph_service is not None and hasattr(graph_service, "repository")
        else None
    )
    ingestion_service = build_ingestion_service(
        settings=settings,
        provider=provider,
        graph_service=graph_service,
        state_runner=state_runner,
        router=router,
        semantic_search_service=semantic_search_service,
        owner_manager=owner_manager,
        execute_write_plan=settings.ingestion_execute_write_plan,
        agentic_runtime=agentic_runtime,
    )
    owner_snapshot = _owner_snapshot(graph_service, settings.owner_graph_node_id)
    owner_profile_reader = (
        OwnerProfileReader(
            graph_service=graph_service,
            owner_manager=owner_manager,
        )
        if owner_manager is not None
        else None
    )
    return ChatRuntime(
        store=store,
        agentic_runtime=agentic_runtime,
        graph_service=graph_service,
        ingestion_service=ingestion_service,
        semantic_search_service=semantic_search_service,
        vectorization_service=getattr(ingestion_service, "vectorization_service", None),
        history_service=history_service,
        debug_commands_enabled=settings.chat_debug_commands_enabled,
        ai_flow_debug_enabled=settings.ai_flow_debug_enabled,
        owner_snapshot=owner_snapshot,
        owner_profile_reader=owner_profile_reader,
    )


def _owner_snapshot(graph_service: Any | None, owner_id: str) -> OwnerSnapshot | None:
    if graph_service is None or not hasattr(graph_service, "get_node"):
        return None
    try:
        node = graph_service.get_node(owner_id)
        properties = getattr(node, "properties", None)
        return OwnerSnapshot.from_properties(properties) if isinstance(properties, dict) else None
    except Exception:
        return None


def build_ai_provider(settings: Settings):
    genai_settings = genai_settings_from_app_settings(settings)
    if settings.normalized_llm_provider == "azure_openai":
        return AzureOpenAIProvider(settings=genai_settings)
    return OpenAIProvider(settings=genai_settings)


def build_semantic_search_service(
    *,
    settings: Settings,
    provider: Any,
    graph_service: Any,
    router: StaticModelRouter,
) -> SemanticMemorySearchService:
    return SemanticMemorySearchService(
        graph_service=graph_service,
        embedding_provider=provider,
        vector_store=ChromaVectorStore.from_settings(settings),
        vector_record_store=VectorRecordStore(
            RelationalSessionProvider.from_settings(settings),
        ),
        model_router=router,
        owner_graph_node_id=settings.owner_graph_node_id,
    )


def build_ingestion_service(
    *,
    settings: Settings,
    provider: Any,
    graph_service: Any | None,
    state_runner: AgenticStateRunner,
    router: StaticModelRouter,
    semantic_search_service: Any | None,
    owner_manager: Any | None,
    execute_write_plan: bool,
    agentic_runtime: AgenticRuntime | None = None,
) -> IngestionService | None:
    if graph_service is None:
        return None

    def planner_execution_context(source) -> AgenticToolExecutionContext:
        return AgenticToolExecutionContext(
            graph_service=graph_service,
            current_text=source.raw_text,
            agentic_runtime=agentic_runtime,
            metadata={
                "source_id": source.source_id,
                "source_type": str(source.source_type),
                "channel": str(source.channel),
            },
        )

    return IngestionService(
        reasoning_service=AgenticReasoningService(state_runner),
        planning_service=AgenticPlanningService(state_runner),
        graph_context_builder=WholeSourceGraphContextPackBuilder(
            search_service=semantic_search_service,
            graph_service=graph_service,
            owner_graph_node_id=settings.owner_graph_node_id,
        ),
        identity_lookup_service=DeterministicIdentityLookupService(
            graph_service=graph_service,
            owner_manager=owner_manager,
            owner_graph_node_id=settings.owner_graph_node_id,
            max_candidates=settings.identity_lookup_max_candidates,
        ),
        candidate_context_hydrator=BoundedCandidateContextHydrator(
            graph_service=graph_service,
            owner_graph_node_id=settings.owner_graph_node_id,
            max_relationships=settings.identity_context_max_relationships,
            max_memory_logs=settings.identity_context_max_memory_logs,
            max_summary_chars=settings.identity_context_max_summary_chars,
            max_total_chars=settings.identity_context_max_total_chars,
        ),
        resolution_agent=LLMResolutionProposalAgent(
            provider,
            router=router,
            session_max_tool_calls=settings.llm_max_tool_calls,
            batch_size=settings.ingestion_resolution_batch_size,
        ),
        entity_extractors=[
            EntityExtractor(provider, router=router),
        ],
        relationship_extractors=[
            ClaimExtractor(provider, router=router),
            PerceptionExtractor(provider, router=router),
            RelationshipExtractor(provider, router=router),
            RelationshipContextExtractor(provider, router=router),
            MetadataPatchExtractor(provider, router=router),
            ProfileMemoryExtractor(provider, router=router),
        ],
        execution_context_factory=planner_execution_context,
        write_plan_builder=GraphWritePlanBuilder(),
        write_plan_executor=GraphWritePlanExecutor(graph_service),
        vectorization_service=GraphVectorizationService(
            graph_service=graph_service,
            embedding_provider=provider,
            vector_store=ChromaVectorStore.from_settings(settings),
            vector_record_store=VectorRecordStore(
                RelationalSessionProvider.from_settings(settings),
            ),
            model_router=router,
            owner_graph_node_id=settings.owner_graph_node_id,
        ),
        execute_write_plan=execute_write_plan,
    )
