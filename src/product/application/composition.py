"""Application composition for the implemented conversation and memory-query states."""

from dataclasses import dataclass

from product.agentic.history import AgenticHistorySession
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.application.memory_search import MemorySearchService
from product.application.references import ReferenceContext
from product.application.states.conversation_entry import ConversationEntryState
from product.application.states.memory_query import MemoryQueryState
from product.application.tools.conversation_entry import (
    IngestMemoryHandler,
    build_conversation_entry_toolbox,
)
from product.application.tools.memory_search import (
    MemorySearchRenderLevel,
    build_memory_search_tool,
)
from product.prompts import PromptService


@dataclass(frozen=True)
class ConversationMemoryComposition:
    """Implemented root and child states sharing one history and reference context."""

    conversation_entry: ConversationEntryState
    memory_query: MemoryQueryState
    reference_context: ReferenceContext


def compose_conversation_memory(
    *,
    owner_id: str,
    llm_client: LLMInterfaceCore,
    history_session: AgenticHistorySession,
    prompt_service: PromptService,
    memory_search_service: MemorySearchService,
    reference_context: ReferenceContext,
    ingest_memory: IngestMemoryHandler,
    search_render_level: MemorySearchRenderLevel = MemorySearchRenderLevel.STANDARD,
) -> ConversationMemoryComposition:
    """Assemble the concrete query child behind the conversation-entry tool.

    Dependencies:
        The caller supplies one owner-scoped search service, one runtime history
        session, and one run-scoped reference context. Both states share those
        instances; the AI client retains the only provider tool loop.
    """
    search_tool = build_memory_search_tool(
        owner_id=owner_id,
        service=memory_search_service,
        reference_context=reference_context,
    )
    memory_query = MemoryQueryState(
        llm_client,
        history_session,
        prompt_service,
        search_tool,
        initial_render_level=search_render_level,
    )
    conversation_toolbox = build_conversation_entry_toolbox(
        memory_query_state=memory_query,
        ingest_memory=ingest_memory,
    )
    conversation_entry = ConversationEntryState(
        llm_client,
        history_session,
        prompt_service,
        conversation_toolbox,
    )
    return ConversationMemoryComposition(
        conversation_entry=conversation_entry,
        memory_query=memory_query,
        reference_context=reference_context,
    )
