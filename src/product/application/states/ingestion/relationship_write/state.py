"""Agentic state for durable relationships and append-only relationship history."""

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
from product.application.states.ingestion.node_resolution import (
    NodeResolutionStateResultDTO,
)
from product.application.states.ingestion.relationship_write.models import (
    RelationshipWriteInputDTO,
    RelationshipWriteResultDTO,
)
from product.application.tools.relationship_write import build_relationship_toolbox
from product.graph import GraphRelationshipService
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

RELATIONSHIP_WRITE_PROMPT = PromptReferenceDTO(
    prompt_id="ingestion-relationship-write",
    version="v1",
)


class RelationshipWriteState(BaseAgenticState):
    """Choose and perform grounded direct, context, and state writes."""

    STATE_ID = "ingestion_relationship_write"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        *,
        owner_id: str,
        graph_relationship_service: GraphRelationshipService,
        reference_context: ReferenceContext,
        additional_tools: list[RegisteredTool] | None = None,
        reference_renderer: ReferenceContextRenderer | None = None,
        prompt_reference: PromptReferenceDTO = RELATIONSHIP_WRITE_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.owner_id = owner_id
        self.graph_relationship_service = graph_relationship_service
        self.reference_context = reference_context
        self.additional_tools = list(additional_tools or [])
        self.reference_renderer = reference_renderer or ReferenceContextRenderer()
        self.prompt_reference = prompt_reference
        self._toolbox: ToolBox | None = None

    def write(
        self,
        state_input: RelationshipWriteInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Run relationship writing with inherited history and completed prior states."""
        return self.invoke(self.build_invocation(state_input, invocation_context))

    def build_invocation(
        self,
        state_input: RelationshipWriteInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateInvocationDTO:
        """Assemble the relationship prompt, result contract, and typed toolbox."""
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
                    "memory_context": state_input.memory_context_result.model_dump_json(
                        indent=2
                    ),
                }
            ),
        )
        return AgenticStateInvocationDTO(
            system_prompt=prompt.text,
            selected_history=invocation_context.inherited_history(),
            request=(
                "Write supported durable relationships and any warranted narrative or "
                "time-qualified relationship history, then report confirmed outcomes."
            ),
            response_model=RelationshipWriteResultDTO,
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
        """Resume the same relationship session after clarification completes."""
        return self.resume(
            AgenticStateResumeDTO(
                continuation=continuation,
                tool_results=tool_results,
                response_model=RelationshipWriteResultDTO,
                toolbox=self._get_toolbox(),
                parallel_tool_calls=True,
            )
        )

    def _get_toolbox(self) -> ToolBox:
        if self._toolbox is None:
            self._toolbox = build_relationship_toolbox(
                owner_id=self.owner_id,
                service=self.graph_relationship_service,
                reference_context=self.reference_context,
                additional_tools=self.additional_tools,
            )
        return self._toolbox


class _NodeResolutionEnvelope(BaseModel):
    """Prompt-only object root for completed node-resolution batches."""

    results: list[NodeResolutionStateResultDTO]
