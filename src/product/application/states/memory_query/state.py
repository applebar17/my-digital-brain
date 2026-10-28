"""Configuration and deterministic preparation for the grounded memory-query state."""

from pydantic import BaseModel

from product.agentic.contracts import AgenticStateInvocationDTO, AgenticStateResultDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import AgenticToolInvocationContext, RegisteredTool, ToolBox
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.application.states.memory_query.models import (
    MemoryQueryContextPacket,
    MemoryQueryRequestDTO,
    MemoryQueryResultDTO,
)
from product.application.tools.memory_search import (
    MemorySearchRenderLevel,
    MemorySearchResultRenderer,
    MemorySearchToolInputDTO,
    MemorySearchToolResultDTO,
)
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

MEMORY_QUERY_PROMPT = PromptReferenceDTO(prompt_id="memory-query", version="v1")


class MemoryQueryState(BaseAgenticState):
    """Run initial retrieval and an iterative read-only LLM search session."""

    STATE_ID = "memory_query"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        search_tool: RegisteredTool[MemorySearchToolInputDTO, MemorySearchToolResultDTO],
        *,
        search_renderer: MemorySearchResultRenderer | None = None,
        initial_render_level: MemorySearchRenderLevel = MemorySearchRenderLevel.STANDARD,
        prompt_reference: PromptReferenceDTO = MEMORY_QUERY_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.search_tool = search_tool
        self.search_renderer = search_renderer or MemorySearchResultRenderer()
        self.initial_render_level = initial_render_level
        self.prompt_reference = prompt_reference
        self.toolbox = ToolBox("memory_query", [search_tool])

    def query(
        self,
        request: MemoryQueryRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Prepare bounded context, then run the canonical structured state lifecycle.

        Dependencies:
            `AgenticToolInvocationContext` supplies inherited conversation and
            parent linkage without adding either to the model-facing query DTO.
            The injected `search_tool` owns both initial deterministic retrieval and
            iterative model calls. `MemorySearchResultRenderer` owns prompt detail;
            `PromptService` resolves the exact template; `BaseAgenticState` owns
            history, provider calls, tool looping, and structured result validation.
        """
        context = self._initial_context(request.goal)
        return self.invoke(self.build_invocation(request, invocation_context, context))

    def build_invocation(
        self,
        request: MemoryQueryRequestDTO,
        invocation_context: AgenticToolInvocationContext,
        context: MemoryQueryContextPacket,
    ) -> AgenticStateInvocationDTO:
        """Assemble the effective query-state configuration without calling a provider.

        The caller supplies the deterministic initial-search packet so inspection can
        render the real state configuration without performing storage I/O.
        """
        rendered_search = self.search_renderer.render(
            context.initial_search,
            level=self.initial_render_level,
        )
        if context.initial_search_error is not None:
            rendered_search = (
                f"Initial search could not complete: {context.initial_search_error}\n"
                "The search_memory tool remains available for a corrected retry."
            )
        rendered_prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(values={"initial_memory_context": rendered_search}),
        )
        return AgenticStateInvocationDTO(
            system_prompt=rendered_prompt.text,
            selected_history=invocation_context.inherited_history(),
            request=request.goal,
            response_model=MemoryQueryResultDTO,
            toolbox=self.toolbox,
            parallel_tool_calls=False,
            parent_state_run_id=invocation_context.parent_state_run_id,
            parent_provider_call_id=invocation_context.parent_provider_call_id,
        )

    def _initial_context(self, goal: str) -> MemoryQueryContextPacket:
        try:
            result = self.search_tool.handler(
                MemorySearchToolInputDTO(
                    semantic_query=goal,
                    neighborhood_depth=1,
                    limit=10,
                )
            )
            return MemoryQueryContextPacket(initial_search=result)
        except Exception as error:
            return MemoryQueryContextPacket(
                initial_search=MemorySearchToolResultDTO(),
                initial_search_error=str(error),
            )
