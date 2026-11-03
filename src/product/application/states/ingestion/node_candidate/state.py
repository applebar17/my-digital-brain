"""Configuration and execution of semantic node-candidate generation."""

from pydantic import BaseModel

from product.agentic.contracts import AgenticStateInvocationDTO, AgenticStateResultDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.application.references import ReferenceContextRenderer
from product.application.states.ingestion.node_candidate.models import (
    NodeCandidateSetDTO,
    NodeCandidateStateInputDTO,
)
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

NODE_CANDIDATE_PROMPT = PromptReferenceDTO(
    prompt_id="ingestion-node-candidate",
    version="v1",
)


class NodeCandidateState(BaseAgenticState):
    """Generate typed semantic candidates without lookup, references, or writes."""

    STATE_ID = "ingestion_node_candidate"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        *,
        reference_renderer: ReferenceContextRenderer | None = None,
        prompt_reference: PromptReferenceDTO = NODE_CANDIDATE_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.reference_renderer = reference_renderer or ReferenceContextRenderer()
        self.prompt_reference = prompt_reference

    def generate(
        self,
        state_input: NodeCandidateStateInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Generate candidates from inherited history and completed reasoning context."""
        return self.invoke(self.build_invocation(state_input, invocation_context))

    def build_invocation(
        self,
        state_input: NodeCandidateStateInputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateInvocationDTO:
        """Assemble the effective candidate-state configuration without provider I/O."""
        prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(
                values={
                    "owner_context": self.reference_renderer.render_owner(state_input.owner),
                    "reference_context": self.reference_renderer.render(
                        state_input.known_references,
                        level=1,
                    ),
                    "reasoning_context": state_input.reasoning.model_dump_json(indent=2),
                }
            ),
        )
        return AgenticStateInvocationDTO(
            system_prompt=prompt.text,
            selected_history=invocation_context.inherited_history(),
            request=(
                "Generate the complete typed semantic node-candidate inventory supported "
                "by the inherited conversation."
            ),
            response_model=NodeCandidateSetDTO,
            parent_state_run_id=invocation_context.parent_state_run_id,
            parent_provider_call_id=invocation_context.parent_provider_call_id,
        )
