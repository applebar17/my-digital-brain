"""Functional child-history inheritance across state and workflow tools."""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict

from product.agentic.contracts import AgenticStateInvocationDTO, StateHistory
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import AgenticToolInvocationContext, RegisteredTool, ToolBox
from product.ai.ai_clients.llm_core.tool_call_batch import ToolCallBatchRuntime
from product.ai.ai_clients.protocols.protocol_chat import (
    BorisChatCompletionMessageFunctionToolCall,
    BorisToolFunction,
    ChatRequest,
    ChatResponse,
    Msg,
)
from product.ai.ai_clients.protocols.protocol_tools import (
    ToolCallContextDTO,
    ToolDefinitionDTO,
)
from product.application.workflows.base import BaseWorkflow, WorkflowContext, WorkflowStep


class ChildRequestDTO(BaseModel):
    goal: str


class ChildOutputDTO(BaseModel):
    answer: str


class ChildStepInputDTO(BaseModel):
    selected_history: list[Msg]
    parent_state_run_id: str
    parent_provider_call_id: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RecordingHistorySession(AgenticHistorySession):
    """Retain started-run linkage after normal completion for functional assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.started_states: list[StateHistory] = []

    def start_state(
        self,
        state_id: str,
        selected_history: list[Msg],
        *,
        parent_state_run_id: str | None = None,
        parent_provider_call_id: str | None = None,
    ) -> StateHistory:
        state = super().start_state(
            state_id,
            selected_history,
            parent_state_run_id=parent_state_run_id,
            parent_provider_call_id=parent_provider_call_id,
        )
        self.started_states.append(state)
        return state


class CompletingClient:
    """Complete a state while recording the exact provider request."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.requests: list[ChatRequest] = []

    def handle_params(
        self,
        *,
        system_prompt: str,
        chat_messages: list[Msg],
        **_kwargs: Any,
    ) -> ChatRequest:
        return ChatRequest(
            model="test-model",
            messages=[Msg(role="system", content=system_prompt), *deepcopy(chat_messages)],
        )

    def call(self, request: ChatRequest, _mapping: Any) -> ChatResponse:
        self.requests.append(deepcopy(request))
        return ChatResponse(message=Msg(role="assistant", content=self.response))


class ToolCallingClient(CompletingClient):
    """Simulate one provider-issued tool call through the bound mapping."""

    def __init__(self, tool_name: str) -> None:
        super().__init__("Parent completed.")
        self.tool_name = tool_name
        self.tool_outputs: list[BaseModel] = []

    def call(self, request: ChatRequest, mapping: Any) -> ChatResponse:
        self.requests.append(deepcopy(request))
        output = mapping[self.tool_name].invoke_for_tool_call(
            ToolCallContextDTO(provider_call_id="call-parent-001", tool_name=self.tool_name),
            goal="Process the current request.",
        )
        self.tool_outputs.append(output)
        return ChatResponse(message=Msg(role="assistant", content=self.response))


class ChildStateHandler:
    """Invoke one child state from a registered parent tool."""

    def __init__(self, child_state: BaseAgenticState) -> None:
        self.child_state = child_state

    def __call__(self, request: ChildRequestDTO) -> ChildOutputDTO:
        raise ValueError("This child requires an agentic parent invocation context.")

    def invoke_with_context(
        self,
        request: ChildRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> ChildOutputDTO:
        result = self.child_state.invoke(
            AgenticStateInvocationDTO(
                system_prompt="Child instructions.",
                selected_history=invocation_context.inherited_history(),
                request=request.goal,
                parent_state_run_id=invocation_context.parent_state_run_id,
                parent_provider_call_id=invocation_context.parent_provider_call_id,
            )
        )
        return ChildOutputDTO(answer=result.assistant_message.as_text())


def child_toolbox(name: str, handler: object) -> ToolBox:
    """Build the one typed tool used by both inheritance scenarios."""
    return ToolBox(
        "parent_tools",
        [
            RegisteredTool(
                definition=ToolDefinitionDTO[ChildRequestDTO](
                    name=name,
                    description="Delegate the current request without copying its source content.",
                    input_model=ChildRequestDTO,
                ),
                handler=handler,
            )
        ],
    )


def invoke_parent(tool_name: str, toolbox: ToolBox, session: RecordingHistorySession) -> None:
    """Invoke a parent with history containing content that must and must not propagate."""
    parent = BaseAgenticState(tool_name + "_parent", ToolCallingClient(tool_name), session)  # type: ignore[arg-type]
    result = parent.invoke(
        AgenticStateInvocationDTO(
            system_prompt="Parent instructions.",
            selected_history=[
                Msg(role="system", content="Old system prompt."),
                Msg(role="user", content="Earlier user context.", meta={"trace_id": "hidden"}),
                Msg(role="assistant", content="Earlier assistant context."),
                Msg(role="tool", content="Hidden tool output.", meta={"tool_call_id": "old"}),
                Msg(
                    role="assistant",
                    content=None,
                    meta={"tool_calls": [{"id": "old-call"}]},
                ),
            ],
            request="Current user memory.",
            toolbox=toolbox,
        )
    )
    assert result.outcome == "completed"


def test_parent_state_tool_inherits_conversation_and_links_child_at_start() -> None:
    session = RecordingHistorySession()
    child_client = CompletingClient("Child completed.")
    child_state = BaseAgenticState("child_state", child_client, session)  # type: ignore[arg-type]

    invoke_parent(
        "delegate_to_child",
        child_toolbox("delegate_to_child", ChildStateHandler(child_state)),
        session,
    )

    parent_run, child_run = session.started_states
    assert child_run.parent_state_run_id == parent_run.state_run_id
    assert child_run.parent_provider_call_id == "call-parent-001"
    assert [message.as_text() for message in child_client.requests[0].messages] == [
        "Child instructions.",
        "Earlier user context.",
        "Earlier assistant context.",
        "Current user memory.",
        "Process the current request.",
    ]
    assert all(message.meta == {} for message in child_client.requests[0].messages[1:])


def test_parent_workflow_tool_passes_inherited_history_to_first_child_state() -> None:
    session = RecordingHistorySession()
    child_client = CompletingClient("Workflow child completed.")
    child_state = BaseAgenticState("workflow_child", child_client, session)  # type: ignore[arg-type]

    def prepare_child(context: WorkflowContext) -> ChildStepInputDTO:
        invocation_context = context.invocation_context
        if invocation_context is None:
            raise ValueError("Workflow-backed agentic steps require invocation context.")
        return ChildStepInputDTO(
            selected_history=invocation_context.inherited_history(),
            parent_state_run_id=invocation_context.parent_state_run_id,
            parent_provider_call_id=invocation_context.parent_provider_call_id,
        )

    def run_child(step_input: ChildStepInputDTO) -> ChildOutputDTO:
        result = child_state.invoke(
            AgenticStateInvocationDTO(
                system_prompt="Workflow child instructions.",
                selected_history=step_input.selected_history,
                request="Analyze the inherited request.",
                parent_state_run_id=step_input.parent_state_run_id,
                parent_provider_call_id=step_input.parent_provider_call_id,
            )
        )
        return ChildOutputDTO(answer=result.assistant_message.as_text())

    workflow = BaseWorkflow(
        "test_workflow",
        "Start one child state.",
        [
            WorkflowStep(
                step_id="first_child",
                title="First child",
                description="Invoke the first workflow child.",
                make_input=prepare_child,
                handler=run_child,
                kind="agentic",
                state_id="workflow_child",
            )
        ],
    )

    class WorkflowHandler:
        def __call__(self, request: ChildRequestDTO) -> ChildOutputDTO:
            raise ValueError("This workflow requires an agentic parent invocation context.")

        def invoke_with_context(
            self,
            request: ChildRequestDTO,
            invocation_context: AgenticToolInvocationContext,
        ) -> ChildOutputDTO:
            return workflow.run(request, invocation_context=invocation_context)["first_child"]  # type: ignore[return-value]

    invoke_parent(
        "run_workflow",
        child_toolbox("run_workflow", WorkflowHandler()),
        session,
    )

    parent_run, child_run = session.started_states
    assert child_run.parent_state_run_id == parent_run.state_run_id
    assert child_run.parent_provider_call_id == "call-parent-001"
    assert [message.as_text() for message in child_client.requests[0].messages] == [
        "Workflow child instructions.",
        "Earlier user context.",
        "Earlier assistant context.",
        "Current user memory.",
        "Analyze the inherited request.",
    ]


def test_parallel_registered_tools_receive_their_own_provider_call_context() -> None:
    session = RecordingHistorySession()
    parent = session.start_state(
        "parallel_parent",
        [Msg(role="user", content="Run both operations.")],
    )

    class RecordingHandler:
        def __init__(self) -> None:
            self.call_ids: list[str] = []

        def __call__(self, request: ChildRequestDTO) -> ChildOutputDTO:
            return ChildOutputDTO(answer=request.goal)

        def invoke_with_context(
            self,
            request: ChildRequestDTO,
            invocation_context: AgenticToolInvocationContext,
        ) -> ChildOutputDTO:
            self.call_ids.append(invocation_context.parent_provider_call_id)
            return ChildOutputDTO(answer=request.goal)

    handler = RecordingHandler()
    toolbox = child_toolbox("parallel_child", handler)
    runtime = ToolCallBatchRuntime(
        log=lambda _message, _level: None,
        clamp_for_model=lambda content, _model: content,
    )
    calls = [
        BorisChatCompletionMessageFunctionToolCall(
            id=f"call-{index}",
            type="function",
            function=BorisToolFunction(
                name="parallel_child",
                arguments={"goal": f"operation-{index}"},
            ),
        )
        for index in (1, 2)
    ]

    results = runtime.execute_batch(
        calls,
        toolbox.bind_to_state(session, parent.state_run_id),
        tools_enabled=True,
        state={"tool_calls_processed": 0, "tool_call_cap": 4},
    )

    assert isinstance(results, list)
    assert all(result.tool_output.status == "ok" for result in results)
    assert sorted(handler.call_ids) == ["call-1", "call-2"]
