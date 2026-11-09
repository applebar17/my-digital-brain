"""Agentic state that creates MemoryLogs and Perceptions through typed tools."""

from pydantic import BaseModel

from product.agentic.contracts import (
    AgenticStateInvocationDTO,
    AgenticStateResultDTO,
    AgenticStateResumeDTO,
    PausedStateContinuationDTO,
    ToolCallResultDTO,
)
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import AgenticToolInvocationContext, RegisteredTool, ToolBox
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.application.references import ReferenceContext, ReferenceContextRenderer
from product.application.states.ingestion.memory_context.models import (
    MemoryContextWriteInputDTO,
    MemoryContextWriteResultDTO,
)
from product.application.states.ingestion.node_resolution import (
    NodeResolutionStateResultDTO,
)
from product.application.tools.memory_context import build_memory_context_toolbox
from product.graph import GraphMemoryService
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

MEMORY_CONTEXT_PROMPT = PromptReferenceDTO(
    prompt_id="ingestion-memory-context",
    version="v1",
)


class MemoryContextWriteState(BaseAgenticState):
    """Preserve additive memory atoms and perceptions after node resolution."""

    STATE_ID = "ingestion_memory_context_write"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        *,
        owner_id: str,
        graph_memory_service: GraphMemoryService,
        reference_context: ReferenceContext,
        additional_tools: list[RegisteredTool] | None = None,
        reference_renderer: ReferenceContextRenderer | None = None,
        prompt_reference: PromptReferenceDTO = MEMORY_CONTEXT_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.owner_id = owner_id
        self.graph_memory_service = graph_memory_service
        self.reference_context = reference_context
        self.additional_tools = list(additional_tools or [])
        self.reference_renderer = reference_renderer or ReferenceContextRenderer()
        self.prompt_reference = prompt_reference
        self._toolbox: ToolBox | None = None

    def write(
        self,
        state_input: MemoryContextWriteInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Run the memory/context state with inherited history and resolved refs."""
        return self.invoke(self.build_invocation(state_input, invocation_context))

    def build_invocation(
        self,
        state_input: MemoryContextWriteInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateInvocationDTO:
        """Assemble the effective prompt, result contract, and write toolbox."""
        prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(
                values={
                    "owner_context": self.reference_renderer.render_owner(state_input.owner),
                    "reference_context": self.reference_renderer.render(
                        state_input.references,
                        level=1,
                    ),
                    "reasoning_context": state_input.reasoning.model_dump_json(indent=2),
                    "node_resolution_context": _NodeResolutionEnvelope(
                        results=state_input.node_resolution_results
                    ).model_dump_json(indent=2),
                }
            ),
        )
        return AgenticStateInvocationDTO(
            system_prompt=prompt.text,
            selected_history=invocation_context.inherited_history(),
            request=(
                "Preserve the supported memory atoms and perceptions through the configured "
                "tools, then report confirmed writes and honest deferrals."
            ),
            response_model=MemoryContextWriteResultDTO,
            toolbox=self._get_toolbox(),
            parallel_tool_calls=True,
            parent_state_run_id=invocation_context.parent_state_run_id,
            parent_provider_call_id=invocation_context.parent_provider_call_id,
        )

    def resume_write(
        self,
        continuation: PausedStateContinuationDTO[BaseModel],
        tool_results: list[ToolCallResultDTO],
    ) -> AgenticStateResultDTO[BaseModel]:
        """Resume the same state after its clarification child returns."""
        return self.resume(
            AgenticStateResumeDTO(
                continuation=continuation,
                tool_results=tool_results,
                response_model=MemoryContextWriteResultDTO,
                toolbox=self._get_toolbox(),
                parallel_tool_calls=True,
            )
        )

    def _get_toolbox(self) -> ToolBox:
        if self._toolbox is None:
            self._toolbox = build_memory_context_toolbox(
                owner_id=self.owner_id,
                service=self.graph_memory_service,
                reference_context=self.reference_context,
                additional_tools=self.additional_tools,
            )
        return self._toolbox


class _NodeResolutionEnvelope(BaseModel):
    """Prompt-only object root for completed node-resolution batches."""

    results: list[NodeResolutionStateResultDTO]
