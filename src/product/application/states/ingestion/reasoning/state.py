"""Configuration and execution of ingestion semantic reasoning."""

from pydantic import BaseModel

from product.agentic.contracts import AgenticStateInvocationDTO, AgenticStateResultDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.application.references import ReferenceContextRenderer
from product.application.states.ingestion.reasoning.models import IngestionReasoningResultDTO
from product.application.tools.memory_search import (
    MemorySearchRenderLevel,
    MemorySearchResultRenderer,
)
from product.application.workflows.memory_ingestion.models import IngestionPreparedContextDTO
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

INGESTION_REASONING_PROMPT = PromptReferenceDTO(
    prompt_id="ingestion-reasoning",
    version="v1",
)


class IngestionReasoningState(BaseAgenticState):
    """Interpret inherited conversation before candidates or writes are produced."""

    STATE_ID = "ingestion_reasoning"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        *,
        reference_renderer: ReferenceContextRenderer | None = None,
        search_renderer: MemorySearchResultRenderer | None = None,
        prompt_reference: PromptReferenceDTO = INGESTION_REASONING_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.reference_renderer = reference_renderer or ReferenceContextRenderer()
        self.search_renderer = search_renderer or MemorySearchResultRenderer()
        self.prompt_reference = prompt_reference

    def analyze(
        self,
        prepared: IngestionPreparedContextDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Interpret inherited history using deterministic owner and retrieval context.

        Dependencies:
            `AgenticToolInvocationContext` supplies the exact inherited conversation.
            The prepared DTO supplies only model-safe owner, reference, and retrieval
            context. Renderers own their canonical prompt representation.
        """
        return self.invoke(self.build_invocation(prepared, invocation_context))

    def build_invocation(
        self,
        prepared: IngestionPreparedContextDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateInvocationDTO:
        """Assemble the effective reasoning configuration without calling a provider."""
        prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(
                values={
                    "owner_context": self.reference_renderer.render_owner(prepared.owner),
                    "reference_context": self.reference_renderer.render(
                        prepared.known_references,
                        level=1,
                    ),
                    "retrieved_memory_context": self.search_renderer.render(
                        prepared.retrieved_memory,
                        level=MemorySearchRenderLevel.STANDARD,
                    ),
                    "ingestion_guidance": prepared.request.guidance or "No extra guidance.",
                }
            ),
        )
        return AgenticStateInvocationDTO(
            system_prompt=prompt.text,
            selected_history=invocation_context.inherited_history(),
            request=(
                "Interpret the inherited conversation for memory ingestion. Focus on any "
                "unclear or incoherent user statements that may require clarification."
            ),
            response_model=IngestionReasoningResultDTO,
            parent_state_run_id=invocation_context.parent_state_run_id,
            parent_provider_call_id=invocation_context.parent_provider_call_id,
        )
