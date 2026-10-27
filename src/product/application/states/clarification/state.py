"""Configuration of the clarification child state."""

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
from product.application.interactions import (
    PendingUserQuestionDTO,
    UserQuestionRequestDTO,
    UserQuestionResolutionDTO,
)
from product.application.states.clarification.models import (
    ClarificationRequestDTO,
    ClarificationResultDTO,
)
from product.prompts import PromptReferenceDTO, PromptRenderContextDTO, PromptService

CLARIFICATION_PROMPT = PromptReferenceDTO(prompt_id="clarification", version="v1")


class ClarificationState(BaseAgenticState):
    """Resolve one supplied uncertainty, asking the user only when necessary."""

    STATE_ID = "clarification"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        ask_user_tool: RegisteredTool[
            UserQuestionRequestDTO,
            UserQuestionResolutionDTO,
        ],
        prompt_reference: PromptReferenceDTO = CLARIFICATION_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.prompt_reference = prompt_reference
        self.toolbox = ToolBox("clarification", [ask_user_tool])

    def clarify(
        self,
        request: ClarificationRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Run one focused clarification in an isolated child transcript.

        Dependencies:
            `AgenticToolInvocationContext` supplies inherited conversation and
            parent linkage from the invoking state.
            `PromptService` resolves the configured behavior; the injected
            `ask_user` tool creates a backend-owned interaction when needed;
            `BaseAgenticState` owns provider calls, pause, and structured output.
        """
        rendered_prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(),
        )
        return self.invoke(
            AgenticStateInvocationDTO(
                system_prompt=rendered_prompt.text,
                selected_history=invocation_context.inherited_history(),
                request=request.model_dump_json(indent=2),
                response_model=ClarificationResultDTO,
                toolbox=self.toolbox,
                parallel_tool_calls=False,
                parent_state_run_id=invocation_context.parent_state_run_id,
                parent_provider_call_id=invocation_context.parent_provider_call_id,
            )
        )

    def resume_clarification(
        self,
        continuation: PausedStateContinuationDTO[PendingUserQuestionDTO],
        tool_results: list[ToolCallResultDTO],
    ) -> AgenticStateResultDTO[PendingUserQuestionDTO]:
        """Resume the same child run after the pending user interaction resolves."""
        return self.resume(
            AgenticStateResumeDTO[PendingUserQuestionDTO](
                continuation=continuation,
                tool_results=tool_results,
                response_model=ClarificationResultDTO,
                toolbox=self.toolbox,
                parallel_tool_calls=False,
            )
        )

