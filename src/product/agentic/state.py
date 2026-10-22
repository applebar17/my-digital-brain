"""Base agentic state invocation and optional reasoning/planning stages."""

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel

from product.agentic.contracts import (
    AgenticStageConfigurationDTO,
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

ExecutionStage = Literal["reasoning", "planning", "main"]


class BaseAgenticState:
    """Run configured structured stages and the main conversation through shared clients."""

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
        """Open a state transcript, run configured stages in order, then run the main session.

        Depends on `AgenticHistorySession` for state ownership and pause snapshots,
        `LLMInterfaceCore` for all provider/tool-loop behavior, and caller-provided
        stage configurations for prompts, DTOs, and optional toolboxes. A stage
        cannot advance until its complete tool batch returns and its DTO validates.
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
            return self._run_stages_then_main(state_history, invocation)
        except Exception as error:
            return self._failed_result(state_history, request, error)

    def resume[InteractionDTO: BaseModel](
        self, invocation: AgenticStateResumeDTO[InteractionDTO]
    ) -> AgenticStateResultDTO[InteractionDTO]:
        """Resume the exact paused stage, then continue its configured sequence.

        The continuation cursor is internal. For a staged pause, the continuation
        also carries the untouched canonical state transcript; the paused stage
        transcript is used to finish that same provider tool batch first.
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

            if continuation.execution_stage == "main":
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
                    state_history, request, outcome, invocation.response_model
                )

            stage = self._stage_configuration(invocation, continuation.execution_stage)
            request = self._build_client_request(
                state_history,
                response_model=stage.response_model,
                toolbox=stage.toolbox,
                parallel_tool_calls=stage.parallel_tool_calls,
            )
            outcome = self.llm_client.resume_tool_batch(
                request,
                continuation.tool_batch,
                invocation.tool_results,
                stage.toolbox.tools_mapping if stage.toolbox else {},
            )
            if isinstance(outcome, ToolCallBatchPauseDTO):
                return self._paused_stage_result(
                    state_history,
                    request,
                    outcome,
                    continuation.execution_stage,
                    continuation.main_state_history,
                )

            artifact = self._parse_structured_output(outcome.message, stage.response_model)
            if artifact is None:
                raise ValueError("A configured stage completed without its structured artifact.")
            state_history.messages = deepcopy(
                continuation.main_state_history.messages
                if continuation.main_state_history is not None
                else []
            )
            if continuation.main_state_history is None:
                raise ValueError("A staged continuation is missing its canonical state transcript.")
            return self._run_stages_then_main(
                state_history,
                invocation,
                completed_stage=continuation.execution_stage,
                completed_artifact=artifact,
            )
        except Exception as error:
            return self._failed_result(state_history, request, error)

    def _run_stages_then_main(
        self,
        state_history: StateHistory,
        invocation: AgenticStateInvocationDTO | AgenticStateResumeDTO,
        *,
        completed_stage: ExecutionStage | None = None,
        completed_artifact: BaseModel | None = None,
    ) -> AgenticStateResultDTO:
        """Run only remaining stages in reasoning → planning → main order."""
        reasoning_artifact: BaseModel | None = None
        plan_artifact: BaseModel | None = None

        if completed_stage == "reasoning":
            reasoning_artifact = completed_artifact
        elif completed_stage == "planning":
            plan_artifact = completed_artifact
        else:
            reasoning = invocation.reasoning_stage
            if reasoning is not None:
                outcome = self._call_stage(state_history, invocation, reasoning, "reasoning")
                if isinstance(outcome, AgenticStateResultDTO):
                    return outcome
                reasoning_artifact = outcome

        if completed_stage != "planning":
            planning = invocation.planning_stage
            if planning is not None:
                outcome = self._call_stage(
                    state_history,
                    invocation,
                    planning,
                    "planning",
                    prior_artifact=reasoning_artifact,
                )
                if isinstance(outcome, AgenticStateResultDTO):
                    return outcome
                plan_artifact = outcome

        self._add_artifact_context(state_history, reasoning_artifact, plan_artifact)
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

    def _call_stage(
        self,
        state_history: StateHistory,
        invocation: AgenticStateInvocationDTO | AgenticStateResumeDTO,
        stage: AgenticStageConfigurationDTO,
        stage_name: Literal["reasoning", "planning"],
        *,
        prior_artifact: BaseModel | None = None,
    ) -> BaseModel | AgenticStateResultDTO:
        """Run one isolated structured stage using the canonical history projection."""
        stage_history = state_history.model_copy(deep=True)
        stage_messages = [Msg(role="system", content=stage.system_prompt)]
        stage_messages.extend(deepcopy(state_history.messages[1:]))
        if prior_artifact is not None:
            stage_messages.append(self._artifact_message("Reasoning artifact", prior_artifact))
        stage_history.messages = stage_messages
        request = self._build_client_request(
            stage_history,
            response_model=stage.response_model,
            toolbox=stage.toolbox,
            parallel_tool_calls=stage.parallel_tool_calls,
        )
        outcome = self.llm_client.call(
            request,
            stage.toolbox.tools_mapping if stage.toolbox else {},
        )
        if isinstance(outcome, ToolCallBatchPauseDTO):
            return self._paused_stage_result(
                state_history,
                request,
                outcome,
                stage_name,
                state_history.model_copy(deep=True),
            )
        artifact = self._parse_structured_output(outcome.message, stage.response_model)
        if artifact is None:
            raise ValueError(f"Configured {stage_name} stage returned no structured artifact.")
        return artifact

    def _paused_stage_result(
        self,
        state_history: StateHistory,
        request: ChatRequest,
        outcome: ToolCallBatchPauseDTO[BaseModel],
        stage: Literal["reasoning", "planning"],
        main_state_history: StateHistory | None,
    ) -> AgenticStateResultDTO:
        """Return a pause with the stage cursor and canonical transcript snapshot."""
        state_history.messages = deepcopy(request.messages)
        continuation = self.history_session.pause_state(
            state_history.state_run_id,
            outcome,
            execution_stage=stage,
            main_state_history=main_state_history,
        )
        pending = next(call for call in outcome.calls if call.interaction_request is not None)
        result_type = AgenticStateResultDTO[type(pending.interaction_request.interaction_packet)]
        return result_type(outcome="awaiting_input", continuation=continuation)

    @staticmethod
    def _stage_configuration(
        invocation: AgenticStateResumeDTO,
        stage: Literal["reasoning", "planning"],
    ) -> AgenticStageConfigurationDTO:
        """Retrieve the configured stage needed to resume from its internal cursor."""
        configuration = getattr(invocation, f"{stage}_stage")
        if configuration is None:
            raise ValueError(
                f"Cannot resume the {stage} stage without its original stage configuration."
            )
        return configuration

    @staticmethod
    def _artifact_message(label: str, artifact: BaseModel) -> Msg:
        return Msg(
            role="user",
            content=f"{label} (internal state context):\n{artifact.model_dump_json(indent=2)}",
        )

    def _add_artifact_context(
        self,
        state_history: StateHistory,
        reasoning_artifact: BaseModel | None,
        plan_artifact: BaseModel | None,
    ) -> None:
        """Add the selected artifact to the main prompt without adding a history turn."""
        selected_artifact = plan_artifact if plan_artifact is not None else reasoning_artifact
        if selected_artifact is not None:
            label = "Planning artifact" if plan_artifact is not None else "Reasoning artifact"
            system_prompt = state_history.messages[0].as_text()
            state_history.messages[0] = Msg(
                role="system",
                content=(
                    f"{system_prompt}\n\n"
                    f"{label} (internal state context):\n"
                    f"{selected_artifact.model_dump_json(indent=2)}"
                ),
            )

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
            continuation = self.history_session.pause_state(state_history.state_run_id, outcome)
            pending = next(call for call in outcome.calls if call.interaction_request is not None)
            result_type = AgenticStateResultDTO[type(pending.interaction_request.interaction_packet)]
            return result_type(outcome="awaiting_input", continuation=continuation)

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
        """Validate provider terminal content against its configured DTO once."""
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
