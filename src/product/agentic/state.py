"""Base agentic state invocation and external-input continuation lifecycle."""

from copy import deepcopy

from pydantic import BaseModel

from product.agentic.contracts import (
    AgenticStateInvocationDTO,
    AgenticStateResumeDTO,
    AgenticStateResultDTO,
    PausedStateContinuationDTO,
    StateHistory,
    ToolCallBatchPauseDTO,
)
from product.agentic.history import AgenticHistorySession
from product.agentic.tools.toolbox import ToolBox
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolErrorDTO


class BaseAgenticState:
    """Run one typed state conversation through the shared client and history session."""

    def __init__(
        self,
        state_id: str,
        llm_client: LLMInterfaceCore,
        history_session: AgenticHistorySession,
    ) -> None:
        self.state_id = state_id
        self.llm_client = llm_client
        self.history_session = history_session

    def invoke(self, invocation: AgenticStateInvocationDTO) -> AgenticStateResultDTO[BaseModel]:
        """Start one isolated state transcript and normalize its client outcome.

        Depends on `AgenticHistorySession.start_state` for caller-selected
        history ownership, `LLMInterfaceCore.handle_params` for request
        construction, and `LLMInterfaceCore.call` for provider/tool execution.
        The caller chooses any child history projection; this state only copies
        it into a local run. A paused provider batch returns without a follow-up
        LLM call until every pending interaction has a matching result.
        """
        state_history: StateHistory | None = None
        request: ChatRequest | None = None
        try:
            state_history = self.history_session.start_state(
                self.state_id,
                invocation.selected_history,
                parent_state_run_id=invocation.parent_state_run_id,
                parent_provider_call_id=invocation.parent_provider_call_id,
            )
            state_history.messages.insert(0, Msg(role="system", content=invocation.system_prompt))
            state_history.messages.append(Msg(role="user", content=invocation.request))
            request = self._build_client_request(
                state_history,
                response_model=invocation.response_model,
                toolbox=invocation.toolbox,
                parallel_tool_calls=invocation.parallel_tool_calls,
            )
            outcome = self.llm_client.call(
                request,
                invocation.toolbox.tools_mapping if invocation.toolbox else {},
            )
            return self._map_client_outcome(state_history, request, outcome, invocation.response_model)
        except Exception as error:
            return self._failed_result(state_history, request, error)

    def resume[InteractionDTO: BaseModel](
        self, invocation: AgenticStateResumeDTO[InteractionDTO]
    ) -> AgenticStateResultDTO[InteractionDTO]:
        """Supply available outputs for a paused batch and resume only when complete.

        Depends on the history session to restore the same state run and on
        `LLMInterfaceCore.resume_tool_batch` to match every external result to
        the provider-issued call ID. Partial user answers update the continuation
        but do not trigger an LLM request.
        """
        state_history: StateHistory | None = None
        request: ChatRequest | None = None
        try:
            continuation = invocation.continuation
            if continuation.state_history.state_id != self.state_id:
                raise ValueError(
                    f"Continuation belongs to state '{continuation.state_history.state_id}', "
                    f"not '{self.state_id}'."
                )
            state_history = self.history_session.resume_state(continuation)
            request = self._build_client_request(
                state_history,
                response_model=invocation.response_model,
                toolbox=invocation.toolbox,
                parallel_tool_calls=invocation.parallel_tool_calls,
            )
            outcome = self.llm_client.resume_tool_batch(
                request,
                continuation.tool_batch,
                invocation.tool_results,
                invocation.toolbox.tools_mapping if invocation.toolbox else {},
            )
            return self._map_client_outcome(
                state_history,
                request,
                outcome,
                invocation.response_model,
            )
        except Exception as error:
            return self._failed_result(state_history, request, error)

    def _build_client_request(
        self,
        state_history: StateHistory,
        *,
        response_model: type[BaseModel] | None,
        toolbox: ToolBox | None,
        parallel_tool_calls: bool | None,
    ) -> ChatRequest:
        """Build the provider request from the stored system prompt and local transcript."""
        if not state_history.messages or state_history.messages[0].role != "system":
            raise ValueError("State transcript must begin with this state's system prompt.")
        system_prompt = state_history.messages[0].as_text()
        return self.llm_client.handle_params(
            system_prompt=system_prompt,
            chat_messages=state_history.messages[1:],
            response_format=response_model,
            tools=toolbox.definitions if toolbox else None,
            parallel_tool_calls=parallel_tool_calls,
        )

    def _map_client_outcome(
        self,
        state_history: StateHistory,
        request: ChatRequest,
        outcome: ChatResponse | ToolCallBatchPauseDTO[BaseModel],
        response_model: type[BaseModel] | None,
    ) -> AgenticStateResultDTO:
        """Retain the exact client transcript and map final or paused outcomes."""
        state_history.messages = deepcopy(request.messages)
        if isinstance(outcome, ToolCallBatchPauseDTO):
            continuation = self.history_session.pause_state(
                state_history.state_run_id,
                outcome,
            )
            pending = next(
                call for call in outcome.calls if call.interaction_request is not None
            )
            result_type = AgenticStateResultDTO[
                type(pending.interaction_request.interaction_packet)
            ]
            return result_type(
                outcome="awaiting_input",
                continuation=continuation,
            )

        state_history.messages.append(deepcopy(outcome.message))
        artifact = self._parse_structured_output(outcome.message, response_model)
        self.history_session.complete_state(state_history.state_run_id)
        return AgenticStateResultDTO[BaseModel](
            outcome="completed",
            assistant_message=outcome.message,
            structured_output=artifact,
        )

    @staticmethod
    def _parse_structured_output(
        message: Msg,
        response_model: type[BaseModel] | None,
    ) -> BaseModel | None:
        """Validate the provider's terminal content against the requested DTO once."""
        if response_model is None:
            return None
        content = message.content
        if isinstance(content, response_model):
            return content
        if isinstance(content, str):
            return response_model.model_validate_json(content)
        if isinstance(content, dict):
            return response_model.model_validate(content)
        raise ValueError(
            f"Structured response for {response_model.__name__} was not JSON-compatible."
        )

    def _failed_result(
        self,
        state_history: StateHistory | None,
        request: ChatRequest | None,
        error: Exception,
    ) -> AgenticStateResultDTO[BaseModel]:
        """Release a failed run and return a readable error to its invoker."""
        if state_history is not None:
            if request is not None:
                state_history.messages = deepcopy(request.messages)
            try:
                self.history_session.complete_state(state_history.state_run_id)
            except ValueError:
                pass
        return AgenticStateResultDTO[BaseModel](
            outcome="failed",
            error=ToolErrorDTO(
                code="agentic_state_failed",
                message=f"State '{self.state_id}' failed with {type(error).__name__}: {error}",
                hint="Review the state error and correct the invocation or runtime configuration.",
            ),
        )
