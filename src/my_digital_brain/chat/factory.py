from __future__ import annotations

from typing import Any

from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime import AgenticRuntime, AgenticStateRunner
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ai.client.settings import genai_settings_from_app_settings
from my_digital_brain.ai.providers import AzureOpenAIProvider, OpenAIProvider
from my_digital_brain.ai.router import StaticModelRouter
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import ChatSessionStore
from my_digital_brain.chat.tool_facade import (
    LLMGraphContextAnswerGenerator,
    MemoryBackendToolFacade,
)
from my_digital_brain.config import Settings
from my_digital_brain.ingestion.agentic_planner import AgenticIngestionPlanner
from my_digital_brain.ingestion.context_retriever import GraphIngestionContextRetriever
from my_digital_brain.ingestion.executor import GraphWritePlanExecutor
from my_digital_brain.ingestion.extractors import (
    ClaimExtractor,
    EntityExtractor,
    MetadataPatchExtractor,
    PerceptionExtractor,
    RelationshipContextExtractor,
    RelationshipExtractor,
)
from my_digital_brain.ingestion.mention_scanner import LLMMentionScanner
from my_digital_brain.ingestion.resolution import ConservativeResolutionService
from my_digital_brain.ingestion.service import IngestionService
from my_digital_brain.ingestion.session_store import InMemoryIngestionProcessStore
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder
from my_digital_brain.rag import GraphVectorizationService, VectorRecordStore
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.vector import ChromaVectorStore


def build_chat_runtime(
    *,
    settings: Settings,
    store: ChatSessionStore,
    graph_service: Any | None = None,
) -> ChatRuntime:
    """Build the production chat runtime from app settings.

    If provider construction fails, return a runtime that responds through the
    normal chat response shape instead of failing FastAPI dependency creation.
    """

    if settings.chat_runtime_mode == "deterministic":
        return ChatRuntime(
            store=store,
            tool_facade=MemoryBackendToolFacade(graph_service=graph_service),
            runtime_mode="deterministic",
            graph_service=graph_service,
            debug_commands_enabled=settings.chat_debug_commands_enabled,
        )

    try:
        provider = build_ai_provider(settings)
    except RuntimeError as exc:
        return ChatRuntime(
            store=store,
            tool_facade=MemoryBackendToolFacade(graph_service=graph_service),
            runtime_mode="deterministic",
            graph_service=graph_service,
            debug_commands_enabled=settings.chat_debug_commands_enabled,
            runtime_unavailable_reason=str(exc),
        )

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
    ingestion_service = build_ingestion_service(
        settings=settings,
        provider=provider,
        graph_service=graph_service,
        state_runner=state_runner,
        router=router,
        execute_write_plan=settings.ingestion_execute_write_plan,
    )
    facade = MemoryBackendToolFacade(
        graph_service=graph_service,
        ingestion_service=ingestion_service,
        answer_generator=LLMGraphContextAnswerGenerator(provider, router=router),
    )
    return ChatRuntime(
        store=store,
        tool_facade=facade,
        runtime_mode="agentic",
        agentic_runtime=agentic_runtime,
        graph_service=graph_service,
        ingestion_service=ingestion_service,
        history_service=history_service,
        debug_commands_enabled=settings.chat_debug_commands_enabled,
    )


def build_ai_provider(settings: Settings):
    genai_settings = genai_settings_from_app_settings(settings)
    if settings.normalized_llm_provider == "azure_openai":
        return AzureOpenAIProvider(settings=genai_settings)
    return OpenAIProvider(settings=genai_settings)


def build_ingestion_service(
    *,
    settings: Settings,
    provider: Any,
    graph_service: Any | None,
    state_runner: AgenticStateRunner,
    router: StaticModelRouter,
    execute_write_plan: bool,
) -> IngestionService | None:
    if graph_service is None:
        return None

    def planner_execution_context(source) -> AgenticToolExecutionContext:
        return AgenticToolExecutionContext(
            graph_service=graph_service,
            current_text=source.raw_text,
            metadata={
                "source_id": source.source_id,
                "source_type": str(source.source_type),
                "channel": str(source.channel),
            },
        )

    return IngestionService(
        scanner=LLMMentionScanner(provider, router=router),
        context_retriever=GraphIngestionContextRetriever(graph_service),
        planner=AgenticIngestionPlanner(
            state_runner,
            structured_provider=provider,
            execution_context_factory=planner_execution_context,
        ),
        extractors=[
            EntityExtractor(provider, router=router),
            ClaimExtractor(provider, router=router),
            PerceptionExtractor(provider, router=router),
            RelationshipExtractor(provider, router=router),
            RelationshipContextExtractor(provider, router=router),
            MetadataPatchExtractor(provider, router=router),
        ],
        resolution_service=ConservativeResolutionService(graph_service),
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
        ),
        execute_write_plan=execute_write_plan,
        process_store=InMemoryIngestionProcessStore(),
    )
