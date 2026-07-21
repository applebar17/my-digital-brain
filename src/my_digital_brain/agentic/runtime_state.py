from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime_helpers import (
    _chat_message_to_frame_dict,
    _state_value,
    _structured_summary,
    _system_prompt_with_runtime_context,
    _trace_json_section,
)
from my_digital_brain.agentic.runtime_models import (
    AgenticStateInvocation,
    AgenticStateRunResult,
)
from my_digital_brain.agentic.state import AgenticStateConfig, default_state_configs
from my_digital_brain.agentic.tools import (
    AgenticToolExecutionContext,
    AgenticToolRegistry,
    build_agentic_tool_mapping,
    build_agentic_toolbox,
    default_agentic_tool_registry,
)
from my_digital_brain.ai.protocols import LLMProvider, ModelRouter
from my_digital_brain.ai.router import StaticModelRouter
from my_digital_brain.ai.schemas import (
    AIRequestContext,
    ChatMessage,
)
from my_digital_brain.ai.session import (
    LLMSessionAwaitingTool,
    LLMSessionFailed,
    LLMSessionRequest,
)
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.debug import AIFlowTraceSection, record_ai_flow_event
from my_digital_brain.prompts import PromptRegistry

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AgenticStateRunner:
    provider: LLMProvider
    model_router: ModelRouter = field(default_factory=StaticModelRouter)
    prompt_registry: PromptRegistry = field(default_factory=PromptRegistry)
    state_configs: dict[AgenticStateId, AgenticStateConfig] = field(
        default_factory=default_state_configs,
    )
    tool_registry: AgenticToolRegistry = field(default_factory=default_agentic_tool_registry)
    history_service: AgenticHistoryService = field(default_factory=AgenticHistoryService)
    temperature: float = 0.2
    max_tokens: int | None = None

    @traceable(name="Agentic State Run", run_type="chain")
    def run_state(self, invocation: AgenticStateInvocation) -> AgenticStateRunResult:
        state_id = AgenticStateId(invocation.state_id)
        state_config = self.state_configs[state_id]
        state_value = _state_value(state_config.state_id)
        model_task = state_config.model_task or state_value
        context = AIRequestContext(
            purpose=model_task,
            prompt_id=state_config.prompt_id,
            prompt_version=state_config.prompt_version,
            metadata={"state_id": state_value},
        )
        route = self.model_router.route(model_task, context)
        tools_disabled = bool(invocation.metadata.get("disable_tools"))
        toolbox = (
            ToolBox(name=f"agentic:{state_config.state_id}:disabled", tools=[], tools_by_name={})
            if tools_disabled
            else build_agentic_toolbox(state_config, self.tool_registry)
        )
        invocation.execution_context.frame_id = invocation.execution_context.frame_id or new_uuid()
        invocation.execution_context.current_payload = invocation.context_payload
        event_start = len(invocation.execution_context.tool_events)
        tools_mapping = (
            {}
            if tools_disabled
            else build_agentic_tool_mapping(
                state_config,
                invocation.execution_context,
                self.tool_registry,
            )
        )
        prompt_id = str(invocation.metadata.get("prompt_id_override") or state_config.prompt_id)
        prompt_version = str(
            invocation.metadata.get("prompt_version_override") or state_config.prompt_version
        )
        prompt = self.prompt_registry.load(
            prompt_id,
            prompt_version,
        ).template
        model_context_payload = self.history_service.model_payload_for_state(
            state_id,
            invocation.context_payload,
        )
        prompt_context_payload = self.history_service.model_prompt_context_for_state(
            state_id,
            invocation.context_payload,
        )
        model_messages = self.history_service.model_messages_for_state(
            state_id,
            invocation.context_payload,
            current_text=invocation.execution_context.current_text,
        )
        expected_output = {
            "allowed_tools": sorted(toolbox.tools_by_name),
            "max_tool_calls": 0 if tools_disabled else state_config.max_tool_calls,
            "owner_finalization": bool(invocation.metadata.get("owner_finalization")),
        }
        prompt = self.system_prompt_with_runtime_context(
            prompt,
            model_context_payload,
            prompt_context=prompt_context_payload,
            runtime_metadata=invocation.metadata,
            expected_output=expected_output,
        )
        record_ai_flow_event(
            title=f"{state_value} - State Input",
            call_kind="agentic_state_input",
            state_id=state_value,
            purpose=model_task,
            model=route.model,
            prompt_id=state_config.prompt_id,
            toolbox_name=toolbox.name,
            sections=[
                AIFlowTraceSection(
                    title="SYSTEM PROMPT",
                    content=prompt,
                    content_type="text",
                ),
                _trace_json_section(
                    "MESSAGES",
                    [
                        message.model_dump(mode="json", exclude_none=True)
                        for message in model_messages
                    ],
                ),
                _trace_json_section("STATE CONTEXT", prompt_context_payload),
                _trace_json_section("EXPECTED OUTPUT", expected_output),
            ],
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        request = LLMSessionRequest(
            system_prompt=prompt,
            model=route.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=model_messages,
            toolbox=toolbox,
            tools_mapping=tools_mapping,
            max_tool_calls=0 if tools_disabled else state_config.max_tool_calls,
            session_id=invocation.execution_context.frame_id or new_uuid(),
            context=context,
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        result = self.provider.run_session(request)
        if isinstance(result, LLMSessionAwaitingTool):
            return self._awaiting_tool_state_result(
                state_config,
                request,
                invocation,
                event_start,
                result,
                route=route,
            )
        if isinstance(result, LLMSessionFailed):
            return AgenticStateRunResult(
                state_id=state_id,
                assistant_text=result.error,
                message_delta=result.messages[1 + len(model_messages) :],
                tool_events=invocation.execution_context.tool_events[event_start:],
                terminal=True,
                status="error",
                metadata={
                    "provider": route.provider,
                    "model": route.model,
                    "route": route.model_dump(mode="json", exclude_none=True),
                    "error": result.error,
                },
            )
        tool_events = invocation.execution_context.tool_events[event_start:]
        has_error = any(
            event.status not in {"ok", "accepted", "pending", "interrupted"}
            for event in tool_events
        )
        state_run_result = AgenticStateRunResult(
            state_id=state_id,
            assistant_text=result.content or None,
            message_delta=result.messages[1 + len(model_messages) :],
            tool_events=tool_events,
            terminal=True,
            status="error" if has_error else "ok",
            metadata={
                "provider": result.metadata.provider,
                "model": result.metadata.model,
                "route": route.model_dump(mode="json", exclude_none=True),
            },
        )
        record_ai_flow_event(
            title=f"{state_value} - State Output",
            call_kind="agentic_state_output",
            state_id=state_value,
            purpose=model_task,
            model=route.model,
            prompt_id=state_config.prompt_id,
            toolbox_name=toolbox.name,
            status=state_run_result.status,
            sections=[
                AIFlowTraceSection(
                    title="LLM OUTPUT",
                    content=state_run_result.assistant_text or "",
                    content_type="text",
                ),
                _trace_json_section(
                    "MESSAGE DELTA",
                    [
                        message.model_dump(mode="json", exclude_none=True)
                        for message in state_run_result.message_delta
                    ],
                ),
                _trace_json_section(
                    "TOOL OUTPUTS",
                    [event.model_dump(mode="json", exclude_none=True) for event in tool_events],
                ),
                _trace_json_section(
                    "ERROR / DIAGNOSTICS",
                    {
                        "terminal": state_run_result.terminal,
                        "status": state_run_result.status,
                    },
                ),
            ],
            metadata=state_run_result.metadata,
        )
        return state_run_result

    @traceable(name="Agentic Structured State Run", run_type="parser")
    def run_structured_state(
        self,
        invocation: AgenticStateInvocation,
        *,
        output_schema: type[BaseModel],
    ) -> AgenticStateRunResult:
        state_id = AgenticStateId(invocation.state_id)
        state_config = self.state_configs[state_id]
        state_value = _state_value(state_config.state_id)
        model_task = state_config.model_task or state_value
        context = AIRequestContext(
            purpose=model_task,
            prompt_id=state_config.prompt_id,
            prompt_version=state_config.prompt_version,
            schema_id=output_schema.__name__,
            metadata={"state_id": state_value, "structured_output": True},
        )
        route = self.model_router.route(model_task, context)
        prompt_id = str(invocation.metadata.get("prompt_id_override") or state_config.prompt_id)
        prompt_version = str(
            invocation.metadata.get("prompt_version_override") or state_config.prompt_version
        )
        prompt = self.prompt_registry.load(
            prompt_id,
            prompt_version,
        ).template
        model_context_payload = self.history_service.model_payload_for_state(
            state_id,
            invocation.context_payload,
        )
        prompt_context_payload = self.history_service.model_prompt_context_for_state(
            state_id,
            invocation.context_payload,
        )
        model_messages = self.history_service.model_messages_for_state(
            state_id,
            invocation.context_payload,
            current_text=invocation.execution_context.current_text,
        )
        expected_output = {"schema": output_schema.__name__}
        prompt = self.system_prompt_with_runtime_context(
            prompt,
            model_context_payload,
            prompt_context=prompt_context_payload,
            runtime_metadata=invocation.metadata,
            expected_output=expected_output,
        )
        record_ai_flow_event(
            title=f"{state_value} - Structured State Input",
            call_kind="agentic_structured_state_input",
            state_id=state_value,
            purpose=model_task,
            model=route.model,
            prompt_id=state_config.prompt_id,
            schema_id=output_schema.__name__,
            sections=[
                AIFlowTraceSection(
                    title="SYSTEM PROMPT",
                    content=prompt,
                    content_type="text",
                ),
                _trace_json_section(
                    "MESSAGES",
                    [
                        message.model_dump(mode="json", exclude_none=True)
                        for message in model_messages
                    ],
                ),
                _trace_json_section("STATE CONTEXT", prompt_context_payload),
                _trace_json_section("EXPECTED OUTPUT", expected_output),
            ],
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        result = self.provider.run_session(
            LLMSessionRequest(
                system_prompt=prompt,
                messages=model_messages,
                model=route.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                output_schema=output_schema,
                toolbox=build_agentic_toolbox(state_config, self.tool_registry),
                tools_mapping=build_agentic_tool_mapping(
                    state_config,
                    invocation.execution_context,
                    self.tool_registry,
                ),
                max_tool_calls=state_config.max_tool_calls,
                session_id=invocation.execution_context.frame_id or new_uuid(),
                context=context,
                metadata={"route": route.model_dump(mode="json", exclude_none=True)},
            ),
        )
        if isinstance(result, LLMSessionAwaitingTool):
            return self._awaiting_tool_state_result(
                state_config,
                LLMSessionRequest(
                    system_prompt=prompt,
                    messages=model_messages,
                    output_schema=output_schema,
                    session_id=result.session_id,
                ),
                invocation,
                len(invocation.execution_context.tool_events),
                result,
                route=route,
            )
        if isinstance(result, LLMSessionFailed) or result.parsed is None:
            error = (
                result.error
                if isinstance(result, LLMSessionFailed)
                else "Structured output was empty."
            )
            return AgenticStateRunResult(
                state_id=state_id,
                assistant_text=error,
                status="error",
                metadata={
                    "provider": route.provider,
                    "model": route.model,
                    "route": route.model_dump(mode="json", exclude_none=True),
                    "error": error,
                },
            )
        parsed = result.parsed
        structured_output = parsed.model_dump(mode="json", exclude_none=True)
        assistant_text = _structured_summary(parsed)
        state_run_result = AgenticStateRunResult(
            state_id=state_id,
            assistant_text=assistant_text,
            message_delta=[ChatMessage(role="assistant", content=assistant_text)],
            structured_output=structured_output,
            terminal=True,
            status="ok",
            metadata={
                "provider": result.metadata.provider if result.metadata else route.provider,
                "model": result.metadata.model,
                "route": route.model_dump(mode="json", exclude_none=True),
                "structured_output_schema": output_schema.__name__,
            },
        )
        record_ai_flow_event(
            title=f"{state_value} - Structured State Output",
            call_kind="agentic_structured_state_output",
            state_id=state_value,
            purpose=model_task,
            model=route.model,
            prompt_id=state_config.prompt_id,
            schema_id=output_schema.__name__,
            status=state_run_result.status,
            sections=[
                AIFlowTraceSection(
                    title="LLM OUTPUT",
                    content=state_run_result.assistant_text or "",
                    content_type="text",
                ),
                _trace_json_section("PARSED STRUCTURED OUTPUT", structured_output),
            ],
            metadata=state_run_result.metadata,
        )
        return state_run_result

    def system_prompt_with_runtime_context(
        self,
        prompt: str,
        payload: Any,
        *,
        prompt_context: Any | None = None,
        runtime_metadata: dict[str, Any] | None = None,
        expected_output: dict[str, Any] | None = None,
    ) -> str:
        return _system_prompt_with_runtime_context(
            prompt,
            payload,
            prompt_context=prompt_context,
            runtime_metadata=runtime_metadata,
            expected_output=expected_output,
        )

    def _awaiting_tool_state_result(
        self,
        state_config: AgenticStateConfig,
        request: LLMSessionRequest,
        invocation: AgenticStateInvocation,
        event_start: int,
        result: LLMSessionAwaitingTool,
        *,
        route: Any,
    ) -> AgenticStateRunResult:
        frame_id = invocation.execution_context.frame_id or new_uuid()
        messages = [_chat_message_to_frame_dict(message) for message in result.messages]
        pending_result = result.continuation.pending_tool_call
        packet = None
        pending_events = [
            event for event in result.tool_events if event.call_id == pending_result.call_id
        ]
        pending_data = (
            pending_events[-1].result.data
            if pending_events and isinstance(pending_events[-1].result.data, dict)
            else {}
        )
        if isinstance(pending_data, dict):
            packet = pending_data.get("clarification_packet")
            if isinstance(packet, dict):
                packet = dict(packet)
                packet.setdefault("tool_call_id", pending_result.call_id)
                packet.setdefault("tool_name", pending_result.name)
        tool_events = invocation.execution_context.tool_events[event_start:]
        interruption_owner = None
        parent_frame_id = invocation.execution_context.parent_frame_id
        if isinstance(pending_data, dict):
            interruption_owner = pending_data.get("interruption_owner")
            if interruption_owner == "child":
                frame_id = str(pending_data.get("child_frame_id") or frame_id)
                parent_frame_id = (
                    str(pending_data.get("parent_frame_id") or parent_frame_id or "") or None
                )
                packet = pending_data.get("clarification_packet") or packet
        return AgenticStateRunResult(
            state_id=state_config.state_id,
            assistant_text=pending_events[-1].result.output if pending_events else None,
            message_delta=[
                ChatMessage.model_validate(message)
                for message in messages[1 + len(request.messages) :]
                if message.get("role") in {"assistant", "tool"}
            ],
            tool_events=tool_events,
            terminal=False,
            status="interrupted",
            metadata={
                "provider": route.provider,
                "model": route.model,
                "route": route.model_dump(mode="json", exclude_none=True),
                "interruption": {
                    "interruption_owner": interruption_owner,
                    "frame_id": frame_id,
                    "state_id": (
                        str(pending_data.get("child_state_id"))
                        if pending_data.get("child_state_id")
                        else _state_value(state_config.state_id)
                    ),
                    "tool_call_id": pending_result.call_id,
                    "tool_name": pending_result.name,
                    "messages": messages,
                    "clarification_packet": packet,
                    "parent_frame_id": parent_frame_id,
                    "parent_tool_call_id": invocation.execution_context.parent_tool_call_id,
                },
            },
        )

    def continue_state_from_messages(
        self,
        *,
        state_id: AgenticStateId,
        messages: list[dict[str, Any]],
        execution_context: AgenticToolExecutionContext,
        metadata: dict[str, Any] | None = None,
    ) -> AgenticStateRunResult:
        state_config = self.state_configs[state_id]
        state_value = _state_value(state_config.state_id)
        model_task = state_config.model_task or state_value
        context = AIRequestContext(
            purpose=model_task,
            prompt_id=state_config.prompt_id,
            prompt_version=state_config.prompt_version,
            metadata={"state_id": state_value, **(metadata or {})},
        )
        route = self.model_router.route(model_task, context)
        toolbox = build_agentic_toolbox(state_config, self.tool_registry)
        event_start = len(execution_context.tool_events)
        execution_context.state_id = state_value
        execution_context.current_payload = None
        tools_mapping = build_agentic_tool_mapping(
            state_config,
            execution_context,
            self.tool_registry,
        )
        request = LLMSessionRequest(
            system_prompt="",
            model=route.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[ChatMessage.model_validate(message) for message in messages],
            toolbox=toolbox,
            tools_mapping=tools_mapping,
            max_tool_calls=state_config.max_tool_calls,
            session_id=execution_context.frame_id or new_uuid(),
            context=context,
            metadata={
                "route": route.model_dump(mode="json", exclude_none=True),
                **(metadata or {}),
            },
        )
        result = self.provider.run_session(request)
        if isinstance(result, LLMSessionAwaitingTool):
            return self._awaiting_tool_state_result(
                state_config,
                request,
                AgenticStateInvocation(
                    state_id=state_id,
                    context_payload={},
                    execution_context=execution_context,
                ),
                event_start,
                result,
                route=route,
            )
        if isinstance(result, LLMSessionFailed):
            return AgenticStateRunResult(
                state_id=state_id,
                assistant_text=result.error,
                message_delta=result.messages[len(messages) :],
                tool_events=execution_context.tool_events[event_start:],
                terminal=True,
                status="error",
                metadata={
                    **(metadata or {}),
                    "provider": route.provider,
                    "model": route.model,
                    "route": route.model_dump(mode="json", exclude_none=True),
                    "error": result.error,
                },
            )
        tool_events = execution_context.tool_events[event_start:]
        has_error = any(
            event.status not in {"ok", "accepted", "pending", "interrupted"}
            for event in tool_events
        )
        return AgenticStateRunResult(
            state_id=state_id,
            assistant_text=result.content or None,
            message_delta=result.messages[len(messages) :],
            tool_events=tool_events,
            terminal=True,
            status="error" if has_error else "ok",
            metadata={
                **(metadata or {}),
                "provider": result.metadata.provider if result.metadata else route.provider,
                "model": result.metadata.model,
                "route": route.model_dump(mode="json", exclude_none=True),
            },
        )
