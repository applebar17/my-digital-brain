"""Agentic node identity resolution with typed graph and clarification tools."""

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
from product.application.states.ingestion.node_resolution.models import (
    CandidateIdentityEvidenceDTO,
    NodeResolutionStateInputDTO,
    NodeResolutionStateResultDTO,
)
from product.application.tools.graph_action import build_node_resolution_toolbox
from product.graph import GraphNodeService
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

NODE_RESOLUTION_PROMPT = PromptReferenceDTO(
    prompt_id="ingestion-node-resolution",
    version="v1",
)


class NodeResolutionWriteState(BaseAgenticState):
    """Resolve one candidate batch and perform only explicitly requested node writes."""

    STATE_ID = "ingestion_node_resolution_write"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        *,
        owner_id: str,
        graph_service: GraphNodeService,
        reference_context: ReferenceContext,
        additional_tools: list[RegisteredTool] | None = None,
        reference_renderer: ReferenceContextRenderer | None = None,
        prompt_reference: PromptReferenceDTO = NODE_RESOLUTION_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.owner_id = owner_id
        self.graph_service = graph_service
        self.reference_context = reference_context
        self.additional_tools = list(additional_tools or [])
        self.reference_renderer = reference_renderer or ReferenceContextRenderer()
        self.prompt_reference = prompt_reference
        self._toolboxes_by_batch: dict[str, ToolBox] = {}

    def resolve_batch(
        self,
        state_input: NodeResolutionStateInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Resolve one prepared batch through the shared agentic tool loop."""
        outcome = self.invoke(self.build_invocation(state_input, invocation_context))
        if outcome.outcome != "awaiting_input":
            self._toolboxes_by_batch.pop(self._batch_key(state_input), None)
        return outcome

    def build_invocation(
        self,
        state_input: NodeResolutionStateInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateInvocationDTO:
        """Assemble the batch-specific prompt, output contract, and narrowed toolbox."""
        prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(
                values={
                    "owner_context": self.reference_renderer.render_owner(state_input.owner),
                    "reference_context": self.reference_renderer.render(
                        state_input.references,
                        level=2,
                    ),
                    "candidate_batch": state_input.batch.model_dump_json(indent=2),
                    "identity_evidence": _IdentityEvidenceEnvelope(
                        items=state_input.identity_evidence
                    ).model_dump_json(indent=2),
                }
            ),
        )
        return AgenticStateInvocationDTO(
            system_prompt=prompt.text,
            selected_history=invocation_context.inherited_history(),
            request="Resolve every candidate in this batch and complete any required writes.",
            response_model=NodeResolutionStateResultDTO,
            toolbox=self._toolbox(state_input),
            parallel_tool_calls=True,
            parent_state_run_id=invocation_context.parent_state_run_id,
            parent_provider_call_id=invocation_context.parent_provider_call_id,
        )

    def resume_batch(
        self,
        state_input: NodeResolutionStateInputDTO,
        continuation: PausedStateContinuationDTO[BaseModel],
        tool_results: list[ToolCallResultDTO],
    ) -> AgenticStateResultDTO[BaseModel]:
        """Resume the same batch after a nested clarification interaction completes."""
        outcome = self.resume(
            AgenticStateResumeDTO(
                continuation=continuation,
                tool_results=tool_results,
                response_model=NodeResolutionStateResultDTO,
                toolbox=self._toolbox(state_input),
                parallel_tool_calls=True,
            )
        )
        if outcome.outcome != "awaiting_input":
            self._toolboxes_by_batch.pop(self._batch_key(state_input), None)
        return outcome

    def _toolbox(self, state_input: NodeResolutionStateInputDTO) -> ToolBox:
        key = self._batch_key(state_input)
        toolbox = self._toolboxes_by_batch.get(key)
        if toolbox is None:
            toolbox = build_node_resolution_toolbox(
                owner_id=self.owner_id,
                service=self.graph_service,
                reference_context=self.reference_context,
                batch=state_input.batch,
                additional_tools=self.additional_tools,
            )
            self._toolboxes_by_batch[key] = toolbox
        return toolbox

    @staticmethod
    def _batch_key(state_input: NodeResolutionStateInputDTO) -> str:
        refs = ":".join(item.candidate_ref for item in state_input.batch.candidates)
        return f"{state_input.batch.batch_id}:{refs}"


class _IdentityEvidenceEnvelope(BaseModel):
    """Prompt-only envelope preserving a JSON object root for evidence lists."""

    items: list[CandidateIdentityEvidenceDTO]
