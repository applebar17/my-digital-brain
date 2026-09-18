from __future__ import annotations

from typing import Any

from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime import AgenticRuntime, AgenticStateRunner
from my_digital_brain.ai.client.settings import genai_settings_from_app_settings
from my_digital_brain.ai.providers import AzureOpenAIProvider, OpenAIProvider
from my_digital_brain.ai.router import StaticModelRouter
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import ChatSessionStore
from my_digital_brain.config import Settings
from my_digital_brain.graph.owner import OwnerNodeManager
from my_digital_brain.graph.owner_profile import OwnerProfileReader
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
    vectorization_service = (
        build_vectorization_service(
            settings=settings,
            provider=provider,
            graph_service=graph_service,
            router=router,
        )
        if graph_service is not None
        else None
    )
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
        semantic_search_service=semantic_search_service,
        vectorization_service=vectorization_service,
        history_service=history_service,
        debug_commands_enabled=settings.chat_debug_commands_enabled,
        ai_flow_debug_enabled=settings.ai_flow_debug_enabled,
        owner_context_resolver=owner_manager,
        owner_profile_reader=owner_profile_reader,
    )
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


def build_vectorization_service(
    *,
    settings: Settings,
    provider: Any,
    graph_service: Any | None,
    router: StaticModelRouter,
 ) -> GraphVectorizationService:
    return GraphVectorizationService(
        graph_service=graph_service,
        embedding_provider=provider,
        vector_store=ChromaVectorStore.from_settings(settings),
        vector_record_store=VectorRecordStore(
            RelationalSessionProvider.from_settings(settings),
        ),
        model_router=router,
        owner_graph_node_id=settings.owner_graph_node_id,
    )
