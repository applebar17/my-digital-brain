"""Top-level conversation state for direct responses and memory capabilities."""

from pydantic import BaseModel

from product.agentic.contracts import AgenticStateInvocationDTO, AgenticStateResultDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import ToolBox
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.application.states.conversation_entry.models import ConversationEntryRequestDTO
from product.prompts import (
    PromptReferenceDTO,
    PromptRenderContextDTO,
    PromptService,
)

CONVERSATION_ENTRY_PROMPT = PromptReferenceDTO(
    prompt_id="conversation-entry",
    version="v1",
)


class ConversationEntryState(BaseAgenticState):
    """Configure the root chat state without owning persistence or child implementations."""

    STATE_ID = "conversation_entry"

    def __init__(
        self,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
        prompt_service: PromptService,
        toolbox: ToolBox,
        prompt_reference: PromptReferenceDTO = CONVERSATION_ENTRY_PROMPT,
    ) -> None:
        super().__init__(self.STATE_ID, llm_client, history_session)
        self.prompt_service = prompt_service
        self.toolbox = toolbox
        self.prompt_reference = prompt_reference

    def respond(
        self,
        request: ConversationEntryRequestDTO,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Run one user-facing turn through the canonical agentic state lifecycle.

        Dependencies:
            `PromptService` resolves the exact configured prompt;
            `AgenticHistorySession.master_history` supplies the caller-prepared
            projection; `BaseAgenticState` and `LLMInterfaceCore` own transcript
            and tool-loop behavior. The injected toolbox contains the only two
            model-visible memory capabilities.

        Side effects:
            Invokes the configured LLM client. Conversation persistence remains
            the responsibility of `ConversationApplicationService`.
        """
        return self.invoke(self.build_invocation(request))

    def build_invocation(
        self,
        request: ConversationEntryRequestDTO,
    ) -> AgenticStateInvocationDTO:
        """Assemble the effective root-state configuration without calling a provider."""
        rendered_prompt = self.prompt_service.render(
            self.prompt_reference,
            PromptRenderContextDTO(),
        )
        return AgenticStateInvocationDTO(
            system_prompt=rendered_prompt.text,
            selected_history=self.history_session.master_history,
            request=request.user_message,
            toolbox=self.toolbox,
            parallel_tool_calls=True,
        )
