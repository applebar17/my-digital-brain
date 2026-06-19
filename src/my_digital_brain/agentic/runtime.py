from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from my_digital_brain.agentic.contexts import (
    ContradictionJudgeResultContext,
    ContradictionReviewContext,
    ConversationContext,
)
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime_models import (
    AgenticRunResult,
    AgenticStateInvocation,
    AgenticStateRunResult,
    AgenticToolEvent,
)
from my_digital_brain.agentic.state import AgenticStateConfig, default_state_configs
from my_digital_brain.agentic.tools import (
    AgenticToolExecutionContext,
    AgenticToolRegistry,
    build_agentic_tool_mapping,
    build_agentic_toolbox,
    default_agentic_tool_registry,
)
from my_digital_brain.ai.protocols import ModelRouter, ToolCallingLLMProvider
from my_digital_brain.ai.router import StaticModelRouter
from my_digital_brain.ai.schemas import (
    AIRequestContext,
    ChatMessage,
    ChatRequest,
    StructuredGenerationRequest,
)
from my_digital_brain.ai.client.tool_execution import ToolCallInterruption
from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.debug import AIFlowTraceSection, record_ai_flow_event
from my_digital_brain.prompts import PromptRegistry


@dataclass(slots=True)
class AgenticStateRunner:
    provider: ToolCallingLLMProvider
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
        invocation.execution_context.frame_id = (
            invocation.execution_context.frame_id or new_uuid()
        )
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
        prompt = self.prompt_registry.load(
            state_config.prompt_id,
            state_config.prompt_version,
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
        request = ChatRequest(
            model=route.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                ChatMessage(role="system", content=prompt),
                *model_messages,
            ],
            context=context,
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        try:
            result = self.provider.generate_chat_with_tools(
                request,
                toolbox=toolbox,
                tools_mapping=tools_mapping,
                max_tool_calls=0 if tools_disabled else state_config.max_tool_calls,
            )
        except ToolCallInterruption as exc:
            return self._interrupted_state_result(
                state_config,
                request,
                invocation,
                event_start,
                exc,
                route=route,
            )
        tool_events = invocation.execution_context.tool_events[event_start:]
        has_error = any(
            event.status not in {"ok", "accepted", "interrupted"}
            for event in tool_events
        )
        state_run_result = AgenticStateRunResult(
            state_id=state_id,
            assistant_text=result.content or None,
            message_delta=list(result.message_delta),
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
                    [
                        event.model_dump(mode="json", exclude_none=True)
                        for event in tool_events
                    ],
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
        prompt = self.prompt_registry.load(
            state_config.prompt_id,
            state_config.prompt_version,
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
        provider = self.provider
        if not hasattr(provider, "generate_structured"):
            return AgenticStateRunResult(
                state_id=state_id,
                assistant_text=(
                    f"{state_value} requires structured output provider support "
                    f"for {output_schema.__name__}."
                ),
                status="error",
                metadata={
                    "provider": getattr(provider, "provider_name", "unknown"),
                    "model": route.model,
                    "route": route.model_dump(mode="json", exclude_none=True),
                    "error": "missing_generate_structured",
                },
            )
        try:
            result = provider.generate_structured(  # type: ignore[attr-defined]
                StructuredGenerationRequest(
                    schema=output_schema,
                    system_prompt=prompt,
                    messages=model_messages,
                    model=route.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    context=context,
                    metadata={"route": route.model_dump(mode="json", exclude_none=True)},
                ),
            )
        except ValidationError as exc:
            return AgenticStateRunResult(
                state_id=state_id,
                assistant_text=f"{state_value} returned invalid structured output: {exc}",
                status="error",
                metadata={
                    "provider": getattr(provider, "provider_name", "unknown"),
                    "model": route.model,
                    "route": route.model_dump(mode="json", exclude_none=True),
                    "error": "invalid_structured_output",
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
                "provider": result.metadata.provider,
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

    def _interrupted_state_result(
        self,
        state_config: AgenticStateConfig,
        request: ChatRequest,
        invocation: AgenticStateInvocation,
        event_start: int,
        exc: ToolCallInterruption,
        *,
        route: Any,
    ) -> AgenticStateRunResult:
        frame_id = invocation.execution_context.frame_id or new_uuid()
        messages = [_chat_message_to_frame_dict(message) for message in exc.messages]
        if not messages:
            messages = [
                _chat_message_to_frame_dict(message)
                for message in request.messages
            ]
        packet = None
        if isinstance(exc.result.data, dict):
            packet = exc.result.data.get("clarification_packet")
            if isinstance(packet, dict):
                packet = dict(packet)
                packet.setdefault("tool_call_id", exc.tool_call_id)
                packet.setdefault("tool_name", exc.tool_name)
        tool_events = invocation.execution_context.tool_events[event_start:]
        interruption_owner = None
        parent_frame_id = invocation.execution_context.parent_frame_id
        if isinstance(exc.result.data, dict):
            interruption_owner = exc.result.data.get("interruption_owner")
            if interruption_owner == "child":
                frame_id = str(exc.result.data.get("child_frame_id") or frame_id)
                parent_frame_id = str(exc.result.data.get("parent_frame_id") or parent_frame_id or "") or None
                packet = exc.result.data.get("clarification_packet") or packet
        return AgenticStateRunResult(
            state_id=state_config.state_id,
            assistant_text=exc.result.output,
            message_delta=[
                ChatMessage.model_validate(message)
                for message in messages[len(request.messages) :]
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
                        str(exc.result.data.get("child_state_id"))
                        if isinstance(exc.result.data, dict) and exc.result.data.get("child_state_id")
                        else _state_value(state_config.state_id)
                    ),
                    "tool_call_id": (
                        str(exc.result.data.get("tool_call_id"))
                        if isinstance(exc.result.data, dict) and exc.result.data.get("tool_call_id")
                        else exc.tool_call_id
                    ),
                    "tool_name": (
                        str(exc.result.data.get("tool_name"))
                        if isinstance(exc.result.data, dict) and exc.result.data.get("tool_name")
                        else exc.tool_name
                    ),
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
        request = ChatRequest(
            model=route.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                ChatMessage.model_validate(message)
                for message in messages
            ],
            context=context,
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        try:
            result = self.provider.generate_chat_with_tools(
                request,
                toolbox=toolbox,
                tools_mapping=tools_mapping,
                max_tool_calls=state_config.max_tool_calls,
            )
        except ToolCallInterruption as exc:
            return self._interrupted_state_result(
                state_config,
                request,
                AgenticStateInvocation(
                    state_id=state_id,
                    context_payload={},
                    execution_context=execution_context,
                ),
                event_start,
                exc,
                route=route,
            )
        tool_events = execution_context.tool_events[event_start:]
        has_error = any(
            event.status not in {"ok", "accepted", "interrupted"}
            for event in tool_events
        )
        return AgenticStateRunResult(
            state_id=state_id,
            assistant_text=result.content or None,
            message_delta=list(result.message_delta),
            tool_events=tool_events,
            terminal=True,
            status="error" if has_error else "ok",
            metadata={
                "provider": result.metadata.provider,
                "model": result.metadata.model,
                "route": route.model_dump(mode="json", exclude_none=True),
            },
        )


@dataclass(slots=True)
class AgenticRuntime:
    state_runner: AgenticStateRunner
    max_state_transitions: int = 5

    @traceable(name="Agentic Runtime Run", run_type="chain")
    def run(
        self,
        conversation_context: ConversationContext,
        execution_context: AgenticToolExecutionContext,
        start_state: AgenticStateId | None = None,
        start_payload: Any | None = None,
    ) -> AgenticRunResult:
        current_state = start_state or self._entry_state(conversation_context)
        current_payload: Any = start_payload if start_payload is not None else conversation_context
        execution_context.agentic_runtime = self
        execution_context.conversation_context = conversation_context
        state_results: list[AgenticStateRunResult] = []
        compact_trace: list[dict[str, Any]] = []

        state_result = self.state_runner.run_state(
            AgenticStateInvocation(
                state_id=current_state,
                context_payload=current_payload,
                execution_context=execution_context,
            ),
        )
        state_results.append(state_result)
        compact_trace.append(_compact_state_trace(state_result))

        if state_result.status == "interrupted":
            interruption_metadata = dict(state_result.metadata.get("interruption") or {})
            if interruption_metadata.get("interruption_owner") == "child":
                interruption = {
                    "frame_id": interruption_metadata.get("frame_id"),
                    "state_id": interruption_metadata.get("state_id"),
                    "tool_call_id": interruption_metadata.get("tool_call_id"),
                    "tool_name": interruption_metadata.get("tool_name"),
                    "clarification_packet": interruption_metadata.get("clarification_packet"),
                    "parent_frame_id": interruption_metadata.get("parent_frame_id"),
                }
            else:
                interruption = self._persist_interrupted_frame(
                    state_result,
                    conversation_context,
                    execution_context,
                    current_payload,
                    compact_trace,
                )
            return AgenticRunResult(
                final_text=state_result.assistant_text,
                visited_states=[result.state_id for result in state_results],
                state_results=state_results,
                status="interrupted",
                interruption=interruption,
                compact_trace=compact_trace,
                metadata={
                    "user_visible_owner": current_state.value,
                    "interrupted_process": interruption.get("state_id") or current_state.value,
                },
            )

        if current_state == AgenticStateId.CONTRADICTION_REVIEW:
            structured_result = self._run_contradiction_structured_result(
                current_payload,
                state_result,
                execution_context,
            )
            state_results.append(structured_result)
            compact_trace.append(_compact_state_trace(structured_result))
            contradiction_status = _contradiction_runtime_status(structured_result)
            return AgenticRunResult(
                final_text=structured_result.assistant_text,
                visited_states=[result.state_id for result in state_results],
                state_results=state_results,
                status=contradiction_status,
                compact_trace=compact_trace,
                metadata={
                    "contradiction_intent": (
                        structured_result.structured_output or {}
                    ).get("intent"),
                },
            )

        return AgenticRunResult(
            final_text=state_result.assistant_text
            or self.state_runner.history_service.state_result_summary(state_result),
            visited_states=[result.state_id for result in state_results],
            state_results=state_results,
            status=state_result.status,
            compact_trace=compact_trace,
        )

    def run_child_frame(
        self,
        *,
        parent_execution_context: AgenticToolExecutionContext,
        conversation_context: ConversationContext,
        child_state: AgenticStateId,
        child_payload: Any,
        tool_name: str,
    ) -> ToolResult:
        child_context = AgenticToolExecutionContext(
            graph_service=parent_execution_context.graph_service,
            ingestion_service=parent_execution_context.ingestion_service,
            semantic_search_service=parent_execution_context.semantic_search_service,
            vectorization_service=parent_execution_context.vectorization_service,
            chat_store=parent_execution_context.chat_store,
            session_id=parent_execution_context.session_id,
            channel=parent_execution_context.channel,
            conversation_id=parent_execution_context.conversation_id,
            owner_id=parent_execution_context.owner_id,
            sender_id=parent_execution_context.sender_id,
            message_id=parent_execution_context.message_id,
            current_text=parent_execution_context.current_text,
            conversation_history_refs=list(parent_execution_context.conversation_history_refs),
            metadata=dict(parent_execution_context.metadata),
            frame_id=new_uuid(),
            parent_frame_id=parent_execution_context.frame_id,
            parent_tool_call_id=parent_execution_context.current_tool_call_id,
            agentic_runtime=self,
            conversation_context=conversation_context,
        )
        result = self.run(
            conversation_context,
            child_context,
            start_state=child_state,
            start_payload=child_payload,
        )
        if result.status == "interrupted":
            parent_frame = self._persist_waiting_child_frame(
                parent_execution_context,
                conversation_context,
                child_result=result,
                tool_name=tool_name,
            )
            interruption = dict(result.interruption or {})
            return ToolResult(
                status="interrupted",
                output=result.final_text or "Child frame needs clarification.",
                data={
                    "operation": tool_name,
                    "interruption_owner": "child",
                    "parent_frame_id": parent_frame.get("frame_id"),
                    "child_frame_id": interruption.get("frame_id"),
                    "child_state_id": interruption.get("state_id") or child_state.value,
                    "tool_call_id": interruption.get("tool_call_id"),
                    "tool_name": interruption.get("tool_name"),
                    "clarification_packet": interruption.get("clarification_packet"),
                    "summary": result.final_text or "Child frame needs clarification.",
                    "created_refs": [],
                    "updated_refs": [],
                    "affected_graph_ids": [],
                    "refreshed_vector_scopes": [],
                    "diagnostics": result.compact_trace,
                    "suggested_next_action": "Answer the active clarification so the child frame can continue.",
                },
            )
        summary = result.final_text or "Child frame completed."
        return ToolResult(
            status="ok" if result.status == "ok" else result.status,
            output=summary,
            data={
                "operation": tool_name,
                "summary": summary,
                "child_state_id": child_state.value,
                "visited_states": [_state_value(state) for state in result.visited_states],
                "created_refs": _collect_child_payload_values(result, "created_refs"),
                "updated_refs": _collect_child_payload_values(result, "updated_refs"),
                "affected_graph_ids": _collect_child_payload_values(result, "affected_graph_ids"),
                "refreshed_vector_scopes": _collect_child_payload_values(result, "refreshed_vector_scopes"),
                "diagnostics": result.compact_trace,
            },
        )

    def _persist_waiting_child_frame(
        self,
        parent_execution_context: AgenticToolExecutionContext,
        conversation_context: ConversationContext,
        *,
        child_result: AgenticRunResult,
        tool_name: str,
    ) -> dict[str, Any]:
        if parent_execution_context.chat_store is None:
            return {"frame_id": parent_execution_context.frame_id}
        from my_digital_brain.chat.models import AgenticFrame

        frame_id = parent_execution_context.frame_id or new_uuid()
        parent_execution_context.frame_id = frame_id
        messages = list(parent_execution_context.provider_messages)
        if not messages and parent_execution_context.current_tool_call_id:
            messages = [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": parent_execution_context.current_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": parent_execution_context.current_tool_name or tool_name,
                                "arguments": json.dumps(
                                    parent_execution_context.current_tool_arguments,
                                    ensure_ascii=True,
                                    sort_keys=True,
                                    default=str,
                                ),
                            },
                        }
                    ],
                }
            ]
        child_interruption = dict(child_result.interruption or {})
        frame = AgenticFrame(
            frame_id=frame_id,
            session_id=parent_execution_context.session_id or conversation_context.context_id,
            state_id=parent_execution_context.state_id or AgenticStateId.CONVERSATION_ENTRY.value,
            status="waiting_child",
            messages=messages,
            context_payload=_frame_context_payload(
                parent_execution_context.current_payload,
                conversation_context,
            ),
            compact_trace=list(child_result.compact_trace),
            parent_frame_id=parent_execution_context.parent_frame_id,
            parent_tool_call_id=parent_execution_context.parent_tool_call_id,
            active_tool_call_id=parent_execution_context.current_tool_call_id,
            active_tool_name=parent_execution_context.current_tool_name or tool_name,
            metadata={
                "waiting_for_child_frame_id": child_interruption.get("frame_id"),
                "waiting_for_child_state_id": child_interruption.get("state_id"),
                "child_tool_call_id": child_interruption.get("tool_call_id"),
                "child_tool_name": child_interruption.get("tool_name"),
            },
        )
        parent_execution_context.chat_store.save_agentic_frame(frame.session_id, frame)
        return {"frame_id": frame.frame_id, "status": frame.status}

    def _run_contradiction_structured_result(
        self,
        context_payload: Any,
        support_result: AgenticStateRunResult,
        execution_context: AgenticToolExecutionContext,
    ) -> AgenticStateRunResult:
        if isinstance(context_payload, ContradictionReviewContext):
            tool_outputs = self.state_runner.history_service.tool_result_contexts_from_events(
                support_result.tool_events,
            )
            context_payload = context_payload.model_copy(
                update={
                    "prior_tool_outputs": [
                        *context_payload.prior_tool_outputs,
                        *tool_outputs,
                    ],
                },
                deep=True,
            )
        return self.state_runner.run_structured_state(
            AgenticStateInvocation(
                state_id=AgenticStateId.CONTRADICTION_REVIEW,
                context_payload=context_payload,
                execution_context=execution_context,
                metadata={
                    "structured_final_output": True,
                    "support_state_status": support_result.status,
                },
            ),
            output_schema=ContradictionJudgeResultContext,
        )

    def _entry_state(self, conversation_context: ConversationContext) -> AgenticStateId:
        return AgenticStateId.CONVERSATION_ENTRY

    def resume_frame(
        self,
        frame: AgenticFrame,
        execution_context: AgenticToolExecutionContext,
        *,
        clarification_answer_summary: str,
        answer_packet: ClarificationAnswerPacket,
    ) -> AgenticRunResult:
        if not frame.active_tool_call_id:
            return AgenticRunResult(
                final_text="The saved agentic frame has no open tool call to resume.",
                visited_states=[AgenticStateId(frame.state_id)],
                status="error",
                compact_trace=[],
            )
        execution_context.agentic_runtime = self
        execution_context.frame_id = frame.frame_id
        execution_context.parent_frame_id = frame.parent_frame_id
        execution_context.parent_tool_call_id = frame.parent_tool_call_id
        conversation_context = self._conversation_context_from_frame(
            frame,
            fallback_text=clarification_answer_summary,
        )
        execution_context.conversation_context = conversation_context
        tool_result = ToolResult(
            status="ok",
            output=clarification_answer_summary,
            data={
                "operation": "request_user_clarification",
                "clarification_answer_summary": clarification_answer_summary,
                "clarification_answer_packet": answer_packet.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            },
        )
        tool_message = {
            "role": "tool",
            "tool_call_id": frame.active_tool_call_id,
            "content": tool_result.model_dump_json(exclude_none=True),
        }
        resumed_messages = [*frame.messages, tool_message]
        state_id = AgenticStateId(frame.state_id)
        state_result = self.state_runner.continue_state_from_messages(
            state_id=state_id,
            messages=resumed_messages,
            execution_context=execution_context,
            metadata={"resumed_frame_id": frame.frame_id},
        )
        compact_trace = [_compact_state_trace(state_result)]
        if state_result.status == "interrupted":
            interruption = self._persist_interrupted_frame(
                state_result,
                conversation_context,
                execution_context,
                frame.context_payload,
                compact_trace,
                base_messages=resumed_messages,
            )
            return AgenticRunResult(
                final_text=state_result.assistant_text,
                visited_states=[state_result.state_id],
                state_results=[state_result],
                status="interrupted",
                interruption=interruption,
                compact_trace=compact_trace,
            )
        full_messages = [
            *resumed_messages,
            *[
                message.model_dump(mode="json", exclude_none=True)
                for message in state_result.message_delta
            ],
        ]
        self._complete_frame(
            frame,
            execution_context=execution_context,
            full_messages=full_messages,
            state_result=state_result,
        )
        if frame.parent_frame_id and frame.parent_tool_call_id:
            parent = self._load_frame(frame.parent_frame_id, execution_context=execution_context)
            if parent is not None:
                return self._resume_parent_frame(
                    parent,
                    child_frame=frame,
                    child_result=state_result,
                    execution_context=execution_context,
                )
        return AgenticRunResult(
            final_text=(
                state_result.assistant_text
                or self.state_runner.history_service.state_result_summary(state_result)
            ),
            visited_states=[state_result.state_id],
            state_results=[state_result],
            status=state_result.status,
            compact_trace=compact_trace,
            metadata={"resumed_frame_id": frame.frame_id},
        )

    def _resume_parent_frame(
        self,
        parent: AgenticFrame,
        *,
        child_frame: AgenticFrame,
        child_result: AgenticStateRunResult,
        execution_context: AgenticToolExecutionContext,
    ) -> AgenticRunResult:
        if not parent.active_tool_call_id:
            return AgenticRunResult(
                final_text="The parent agentic frame has no open tool call.",
                visited_states=[AgenticStateId(parent.state_id), child_result.state_id],
                state_results=[child_result],
                status="error",
                compact_trace=[_compact_state_trace(child_result)],
            )
        summary = self.state_runner.history_service.state_result_summary(child_result)
        tool_result = ToolResult(
            status="ok" if child_result.status == "ok" else child_result.status,
            output=summary,
            data={
                "operation": parent.active_tool_name or child_frame.state_id,
                "child_frame_id": child_frame.frame_id,
                "child_state_id": child_frame.state_id,
                "summary": summary,
                "child_status": child_result.status,
            },
        )
        tool_message = {
            "role": "tool",
            "tool_call_id": parent.active_tool_call_id,
            "content": tool_result.model_dump_json(exclude_none=True),
        }
        parent_messages = [*parent.messages, tool_message]
        execution_context.frame_id = parent.frame_id
        execution_context.parent_frame_id = parent.parent_frame_id
        execution_context.parent_tool_call_id = parent.parent_tool_call_id
        parent_conversation = self._conversation_context_from_frame(
            parent,
            fallback_text=summary,
        )
        execution_context.conversation_context = parent_conversation
        parent_result = self.state_runner.continue_state_from_messages(
            state_id=AgenticStateId(parent.state_id),
            messages=parent_messages,
            execution_context=execution_context,
            metadata={"resumed_child_frame_id": child_frame.frame_id},
        )
        compact_trace = [_compact_state_trace(child_result), _compact_state_trace(parent_result)]
        if parent_result.status == "interrupted":
            interruption = self._persist_interrupted_frame(
                parent_result,
                parent_conversation,
                execution_context,
                parent.context_payload,
                compact_trace,
                base_messages=parent_messages,
            )
            return AgenticRunResult(
                final_text=parent_result.assistant_text,
                visited_states=[child_result.state_id, parent_result.state_id],
                state_results=[child_result, parent_result],
                status="interrupted",
                interruption=interruption,
                compact_trace=compact_trace,
            )
        full_messages = [
            *parent_messages,
            *[
                message.model_dump(mode="json", exclude_none=True)
                for message in parent_result.message_delta
            ],
        ]
        self._complete_frame(
            parent,
            execution_context=execution_context,
            full_messages=full_messages,
            state_result=parent_result,
        )
        if parent.parent_frame_id and parent.parent_tool_call_id:
            grandparent = self._load_frame(
                parent.parent_frame_id,
                execution_context=execution_context,
            )
            if grandparent is not None:
                return self._resume_parent_frame(
                    grandparent,
                    child_frame=parent,
                    child_result=parent_result,
                    execution_context=execution_context,
                )
        return AgenticRunResult(
            final_text=(
                parent_result.assistant_text
                or self.state_runner.history_service.state_result_summary(parent_result)
            ),
            visited_states=[child_result.state_id, parent_result.state_id],
            state_results=[child_result, parent_result],
            status=parent_result.status,
            compact_trace=compact_trace,
            metadata={
                "resumed_frame_id": parent.frame_id,
                "completed_child_frame_id": child_frame.frame_id,
            },
        )

    def _persist_interrupted_frame(
        self,
        state_result: AgenticStateRunResult,
        conversation_context: ConversationContext,
        execution_context: AgenticToolExecutionContext,
        current_payload: Any,
        compact_trace: list[dict[str, Any]],
        *,
        base_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from my_digital_brain.chat.models import AgenticFrame, ClarificationPacket

        interruption = dict(state_result.metadata.get("interruption") or {})
        frame_id = str(interruption.get("frame_id") or execution_context.frame_id or new_uuid())
        messages = list(interruption.get("messages") or base_messages or [])
        packet_payload = interruption.get("clarification_packet")
        packet = (
            ClarificationPacket.model_validate(packet_payload)
            if isinstance(packet_payload, dict)
            else None
        )
        frame = AgenticFrame(
            frame_id=frame_id,
            session_id=execution_context.session_id or conversation_context.context_id,
            state_id=str(interruption.get("state_id") or state_result.state_id.value),
            status="interrupted",
            messages=messages,
            context_payload=_frame_context_payload(current_payload, conversation_context),
            compact_trace=compact_trace,
            parent_frame_id=interruption.get("parent_frame_id")
            or execution_context.parent_frame_id,
            parent_tool_call_id=interruption.get("parent_tool_call_id")
            or execution_context.parent_tool_call_id,
            active_tool_call_id=(
                str(interruption["tool_call_id"]) if interruption.get("tool_call_id") else None
            ),
            active_tool_name=(
                str(interruption["tool_name"]) if interruption.get("tool_name") else None
            ),
            clarification_packet=packet,
            metadata={
                "interrupted_state": _state_value(state_result.state_id),
                "tool_call_id": interruption.get("tool_call_id"),
                "tool_name": interruption.get("tool_name"),
            },
        )
        if execution_context.chat_store is not None:
            execution_context.chat_store.save_agentic_frame(frame.session_id, frame)
        return {
            "frame_id": frame.frame_id,
            "state_id": frame.state_id,
            "tool_call_id": frame.active_tool_call_id,
            "tool_name": frame.active_tool_name,
            "clarification_packet": (
                frame.clarification_packet.model_dump(mode="json", exclude_none=True)
                if frame.clarification_packet is not None
                else None
            ),
        }

    def _complete_frame(
        self,
        frame: AgenticFrame,
        *,
        execution_context: AgenticToolExecutionContext,
        full_messages: list[dict[str, Any]],
        state_result: AgenticStateRunResult,
    ) -> None:
        if execution_context.chat_store is None:
            return
        execution_context.chat_store.update_agentic_frame_status(
            frame.session_id,
            frame.frame_id,
            "completed" if state_result.status == "ok" else state_result.status,
            metadata={
                "completed_state_status": state_result.status,
                "summary": self.state_runner.history_service.state_result_summary(state_result),
            },
            messages=full_messages,
            clarification_packet=None,
        )

    def _load_frame(
        self,
        frame_id: str,
        *,
        execution_context: AgenticToolExecutionContext,
    ) -> AgenticFrame | None:
        if execution_context.chat_store is None:
            return None
        try:
            return execution_context.chat_store.get_agentic_frame(frame_id)
        except Exception:
            return None

    def _conversation_context_from_frame(
        self,
        frame: AgenticFrame,
        *,
        fallback_text: str,
    ) -> ConversationContext:
        conversation_payload = frame.context_payload.get("conversation")
        if isinstance(conversation_payload, dict):
            try:
                return ConversationContext.model_validate(conversation_payload)
            except Exception:
                pass
        return self.state_runner.history_service.source_conversation_context(
            source_text=fallback_text,
        )

def _contradiction_runtime_status(state_result: AgenticStateRunResult) -> str:
    if state_result.status == "error":
        return "error"
    output = state_result.structured_output or {}
    intent = output.get("intent")
    if intent == "fail_safe":
        return "error"
    if intent == "needs_context":
        return "needs_context"
    return "ok"


def _collect_child_payload_values(result: AgenticRunResult, key: str) -> list[str]:
    values: list[str] = []
    for state_result in result.state_results:
        for event in state_result.tool_events:
            data = event.data or {}
            raw = data.get(key)
            if isinstance(raw, list):
                values.extend(str(item) for item in raw if item)
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _compact_state_trace(state_result: AgenticStateRunResult) -> dict[str, Any]:
    return {
        "state_id": _state_value(state_result.state_id),
        "status": state_result.status,
        "assistant_text": state_result.assistant_text,
        "structured_output": state_result.structured_output,
        "tools": [
            {
                "tool_name": event.tool_name,
                "status": event.status,
                "output": event.output,
                "error": event.error,
            }
            for event in state_result.tool_events
        ],
    }


def _state_value(state_id: AgenticStateId | str) -> str:
    return state_id.value if isinstance(state_id, AgenticStateId) else str(state_id)


def _structured_summary(parsed: BaseModel) -> str:
    if isinstance(parsed, ContradictionJudgeResultContext):
        if parsed.clarification_question:
            return parsed.clarification_question
        return parsed.reason
    for field_name in ("summary", "reason", "doubt", "question"):
        value = getattr(parsed, field_name, None)
        if isinstance(value, str) and value.strip():
            return value
    return json.dumps(parsed.model_dump(mode="json", exclude_none=True), ensure_ascii=True)


def _trace_json_section(title: str, payload: Any) -> AIFlowTraceSection:
    return AIFlowTraceSection(
        title=title,
        content=json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        content_type="json",
    )


def _chat_message_to_frame_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return {
            key: value
            for key, value in message.items()
            if key in {"role", "content", "name", "tool_calls", "tool_call_id"}
        }
    if hasattr(message, "model_dump"):
        payload = message.model_dump(mode="json", exclude_none=True)
        return {
            key: value
            for key, value in payload.items()
            if key in {"role", "content", "name", "tool_calls", "tool_call_id"}
        }
    return {"role": getattr(message, "role", "assistant"), "content": getattr(message, "content", "")}


def _frame_context_payload(current_payload: Any, conversation: ConversationContext) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "conversation": conversation.model_dump(mode="json", exclude_none=True),
    }
    if hasattr(current_payload, "model_dump"):
        payload["current_payload"] = current_payload.model_dump(mode="json", exclude_none=True)
    elif isinstance(current_payload, dict):
        payload["current_payload"] = current_payload
    else:
        payload["current_payload"] = {"value": str(current_payload)}
    return payload


def _system_prompt_with_runtime_context(
    prompt: str,
    payload: Any,
    *,
    prompt_context: Any | None = None,
    runtime_metadata: dict[str, Any] | None = None,
    expected_output: dict[str, Any] | None = None,
) -> str:
    current_time = _find_prompt_value(payload, "current_time") or "unknown"
    timezone = _find_prompt_value(payload, "timezone") or "UTC"
    sections = [
        prompt.rstrip(),
        (
            "Runtime context:\n"
            f"- current_time: {current_time}\n"
            f"- timezone: {timezone}"
        ),
    ]
    if runtime_metadata:
        sections.append(_system_json_section("Runtime metadata", runtime_metadata))
    if prompt_context not in (None, "", [], {}):
        sections.append(_system_json_section("Process context", prompt_context))
    if expected_output:
        sections.append(_system_json_section("Expected output", expected_output))
    return "\n\n".join(section for section in sections if section).rstrip() + "\n"


def _system_json_section(title: str, payload: Any) -> str:
    return (
        f"{title}:\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}\n"
        "```"
    )


def _find_prompt_value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return value
        for item in payload.values():
            found = _find_prompt_value(item, key)
            if found not in (None, "", [], {}):
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_prompt_value(item, key)
            if found not in (None, "", [], {}):
                return found
    return None
