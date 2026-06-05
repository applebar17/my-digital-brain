from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from my_digital_brain.agentic.contexts import (
    ContradictionJudgeResultContext,
    ContradictionReviewContext,
    ConversationContext,
    CorrectionIntakeContext,
    QueryRetrievalPlanningContext,
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
    max_tokens: int = 800

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
        record_ai_flow_event(
            title=f"{state_value} - State Input",
            call_kind="agentic_state_input",
            state_id=state_value,
            purpose=model_task,
            model=route.model,
            prompt_id=state_config.prompt_id,
            toolbox_name=toolbox.name,
            sections=[
                _trace_json_section("STATE INPUT", model_context_payload),
                _trace_json_section(
                    "EXPECTED OUTPUT",
                    {
                        "allowed_tools": sorted(toolbox.tools_by_name),
                        "max_tool_calls": 0 if tools_disabled else state_config.max_tool_calls,
                        "owner_finalization": bool(
                            invocation.metadata.get("owner_finalization"),
                        ),
                    },
                ),
            ],
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        request = ChatRequest(
            model=route.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                ChatMessage(role="system", content=prompt),
                ChatMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "state_id": state_value,
                            "runtime": invocation.metadata,
                            "context": model_context_payload,
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                ),
            ],
            context=context,
            metadata={"route": route.model_dump(mode="json", exclude_none=True)},
        )
        result = self.provider.generate_chat_with_tools(
            request,
            toolbox=toolbox,
            tools_mapping=tools_mapping,
            max_tool_calls=0 if tools_disabled else state_config.max_tool_calls,
        )
        tool_events = invocation.execution_context.tool_events[event_start:]
        handoff_target, handoff_arguments = _last_handoff(tool_events)
        has_error = any(
            event.status not in {"ok", "accepted", "needs_user_input"}
            for event in tool_events
        )
        state_run_result = AgenticStateRunResult(
            state_id=state_id,
            assistant_text=result.content or None,
            tool_events=tool_events,
            handoff_target=handoff_target,
            handoff_arguments=handoff_arguments,
            terminal=handoff_target is None,
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
                    "TOOL OUTPUTS",
                    [
                        event.model_dump(mode="json", exclude_none=True)
                        for event in tool_events
                    ],
                ),
                _trace_json_section(
                    "ERROR / DIAGNOSTICS",
                    {
                        "handoff_target": state_run_result.handoff_target,
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
        record_ai_flow_event(
            title=f"{state_value} - Structured State Input",
            call_kind="agentic_structured_state_input",
            state_id=state_value,
            purpose=model_task,
            model=route.model,
            prompt_id=state_config.prompt_id,
            schema_id=output_schema.__name__,
            sections=[
                _trace_json_section("STATE INPUT", model_context_payload),
                _trace_json_section("EXPECTED OUTPUT", {"schema": output_schema.__name__}),
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
                    input_message={
                        "state_id": state_value,
                        "runtime": {
                            **invocation.metadata,
                            "structured_output": True,
                            "output_schema": output_schema.__name__,
                        },
                        "context": self.history_service.model_payload_for_state(
                            state_id,
                            invocation.context_payload,
                        ),
                    },
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
        state_run_result = AgenticStateRunResult(
            state_id=state_id,
            assistant_text=_structured_summary(parsed),
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
    ) -> AgenticRunResult:
        current_state = start_state or self._entry_state(conversation_context)
        owner_state = current_state
        current_payload: Any = conversation_context
        state_results: list[AgenticStateRunResult] = []
        compact_trace: list[dict[str, Any]] = []

        for _ in range(self.max_state_transitions):
            state_result = self.state_runner.run_state(
                AgenticStateInvocation(
                    state_id=current_state,
                    context_payload=current_payload,
                    execution_context=execution_context,
                ),
            )
            state_results.append(state_result)
            compact_trace.append(_compact_state_trace(state_result))

            if state_result.handoff_target == "memory_query":
                current_state = AgenticStateId.MEMORY_QUERY
                current_payload = _query_context_from_handoff(
                    conversation_context,
                    state_result.handoff_arguments,
                    self.state_runner.history_service,
                )
                continue

            if state_result.handoff_target == "correction_intake":
                current_state = AgenticStateId.CORRECTION_INTAKE
                current_payload = _correction_context_from_handoff(
                    conversation_context,
                    state_result.handoff_arguments,
                    self.state_runner.history_service,
                )
                continue

            if state_result.handoff_target == "memory_ingestion_precheck":
                return self._run_ingestion_backend(
                    conversation_context,
                    execution_context,
                    state_results,
                    compact_trace,
                    state_result.handoff_arguments,
                    owner_state,
                )

            if state_result.handoff_target == "contradiction_review":
                current_state = AgenticStateId.CONTRADICTION_REVIEW
                current_payload = _contradiction_context_from_handoff(
                    state_result.handoff_arguments,
                )
                continue

            direct_pending_hints = _pending_process_hints([state_result])
            if direct_pending_hints:
                interrupt_text = (
                    state_result.tool_events[-1].output
                    if state_result.tool_events
                    else None
                ) or state_result.assistant_text
                return AgenticRunResult(
                    final_text=interrupt_text,
                    visited_states=[result.state_id for result in state_results],
                    state_results=state_results,
                    status="needs_user_input",
                    pending_process_hints=direct_pending_hints,
                    compact_trace=compact_trace,
                    metadata={
                        "user_visible_owner": current_state.value,
                        "interrupted_process": current_state.value,
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
                pending_hints = _contradiction_pending_process_hints(structured_result)
                if pending_hints:
                    return AgenticRunResult(
                        final_text=(
                            structured_result.structured_output or {}
                        ).get("clarification_question")
                        or structured_result.assistant_text,
                        visited_states=[result.state_id for result in state_results],
                        state_results=state_results,
                        status="needs_user_input",
                        pending_process_hints=pending_hints,
                        compact_trace=compact_trace,
                        metadata={
                            "contradiction_intent": "needs_clarification",
                            "user_visible_owner": AgenticStateId.CONTRADICTION_REVIEW.value,
                        },
                    )
                contradiction_status = _contradiction_runtime_status(structured_result)
                if current_state != owner_state and contradiction_status != "error":
                    final_result = self._finalize_with_owner(
                        owner_state,
                        conversation_context,
                        execution_context,
                        structured_result,
                    )
                    state_results.append(final_result)
                    compact_trace.append(_compact_state_trace(final_result))
                    return AgenticRunResult(
                        final_text=(
                            final_result.assistant_text
                            or self.state_runner.history_service.state_result_summary(
                                structured_result,
                            )
                        ),
                        visited_states=[result.state_id for result in state_results],
                        state_results=state_results,
                        status=final_result.status,
                        pending_process_hints=_pending_process_hints(state_results),
                        compact_trace=compact_trace,
                        metadata={
                            "user_visible_owner": owner_state.value,
                            "completed_process": current_state.value,
                            "contradiction_intent": (
                                structured_result.structured_output or {}
                            ).get("intent"),
                        },
                    )
                return AgenticRunResult(
                    final_text=structured_result.assistant_text,
                    visited_states=[result.state_id for result in state_results],
                    state_results=state_results,
                    status=contradiction_status,
                    pending_process_hints=_pending_process_hints(state_results),
                    compact_trace=compact_trace,
                    metadata={
                        "contradiction_intent": (
                            structured_result.structured_output or {}
                        ).get("intent"),
                    },
                )

            if current_state != owner_state and not _requires_direct_user_visibility(
                state_result,
                state_results,
            ):
                final_result = self._finalize_with_owner(
                    owner_state,
                    conversation_context,
                    execution_context,
                    state_result,
                )
                state_results.append(final_result)
                compact_trace.append(_compact_state_trace(final_result))
                return AgenticRunResult(
                    final_text=(
                        final_result.assistant_text
                        or self.state_runner.history_service.state_result_summary(
                            state_result,
                        )
                    ),
                    visited_states=[result.state_id for result in state_results],
                    state_results=state_results,
                    status=final_result.status,
                    pending_process_hints=_pending_process_hints(state_results),
                    compact_trace=compact_trace,
                    metadata={
                        "user_visible_owner": owner_state.value,
                        "completed_process": current_state.value,
                    },
                )

            return AgenticRunResult(
                final_text=state_result.assistant_text
                or self.state_runner.history_service.state_result_summary(state_result),
                visited_states=[result.state_id for result in state_results],
                state_results=state_results,
                status=state_result.status,
                pending_process_hints=_pending_process_hints(state_results),
                compact_trace=compact_trace,
            )

        return AgenticRunResult(
            final_text="I could not complete the agentic flow because the state transition limit was reached.",
            visited_states=[result.state_id for result in state_results],
            state_results=state_results,
            status="max_transitions_exceeded",
            pending_process_hints=_pending_process_hints(state_results),
            compact_trace=compact_trace,
        )

    def _finalize_with_owner(
        self,
        owner_state: AgenticStateId,
        conversation_context: ConversationContext,
        execution_context: AgenticToolExecutionContext,
        completed_state_result: AgenticStateRunResult,
    ) -> AgenticStateRunResult:
        owner_context = self.state_runner.history_service.owner_finalization_context(
            conversation_context,
            completed_state=completed_state_result,
        )
        return self.state_runner.run_state(
            AgenticStateInvocation(
                state_id=owner_state,
                context_payload=owner_context,
                execution_context=execution_context,
                metadata={
                    "owner_finalization": True,
                    "completed_state": _state_value(completed_state_result.state_id),
                    "disable_tools": True,
                },
            ),
        )

    def _finalize_backend_process_with_owner(
        self,
        owner_state: AgenticStateId,
        conversation_context: ConversationContext,
        execution_context: AgenticToolExecutionContext,
        *,
        process_name: str,
        summary: str,
        data: dict[str, Any],
    ) -> AgenticStateRunResult:
        owner_context = (
            self.state_runner.history_service.owner_finalization_context_from_output(
                conversation_context,
                process_name=process_name,
                summary=summary,
                data=data,
            )
        )
        return self.state_runner.run_state(
            AgenticStateInvocation(
                state_id=owner_state,
                context_payload=owner_context,
                execution_context=execution_context,
                metadata={
                    "owner_finalization": True,
                    "completed_state": process_name,
                    "disable_tools": True,
                },
            ),
        )

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
        if (
            conversation_context.pending_process is not None
            or conversation_context.pending_processes
        ):
            return AgenticStateId.PENDING_PROCESS_REVIEW
        return AgenticStateId.CONVERSATION_ENTRY

    @traceable(name="Agentic Ingestion Backend Handoff", run_type="chain")
    def _run_ingestion_backend(
        self,
        conversation_context: ConversationContext,
        execution_context: AgenticToolExecutionContext,
        state_results: list[AgenticStateRunResult],
        compact_trace: list[dict[str, Any]],
        handoff_arguments: dict[str, Any],
        owner_state: AgenticStateId,
    ) -> AgenticRunResult:
        facade = execution_context.backend_facade
        if facade is None:
            final_text = "Memory ingestion cannot run because backend_facade is not configured."
            status = "error"
            pending_hints = _pending_process_hints(state_results)
        else:
            from my_digital_brain.chat.facade import ChatToolRequest

            request = ChatToolRequest(
                session_id=execution_context.session_id or conversation_context.context_id,
                channel=execution_context.channel,
                conversation_id=(
                    execution_context.conversation_id
                    or conversation_context.context_id
                ),
                owner_id=execution_context.owner_id or "owner",
                text=handoff_arguments.get("source_text")
                or conversation_context.current_message.content
                or "",
                pending_process_context=execution_context.pending_process_context,
                conversation_history_refs=list(execution_context.conversation_history_refs),
                metadata={
                    **execution_context.metadata,
                    **(handoff_arguments.get("metadata") or {}),
                    "source_refs": handoff_arguments.get("source_refs") or [],
                },
            )
            result = facade.start_memory_ingestion(request)
            final_text = result.primary_text
            status = "ok" if str(result.status) != "failed" else "error"
            pending_hints = _pending_process_hints(state_results)
            if result.pending_process is not None:
                pending_hints.append(result.pending_process.model_dump(mode="json"))
            compact_trace.append(
                {
                    "backend_process": "memory_ingestion_precheck",
                    "status": str(result.status),
                    "summary": result.primary_text,
                },
            )
            if status == "ok" and result.pending_process is None:
                final_result = self._finalize_backend_process_with_owner(
                    owner_state,
                    conversation_context,
                    execution_context,
                    process_name="memory_ingestion_precheck",
                    summary=result.primary_text,
                    data=result.model_dump(mode="json", exclude_none=True),
                )
                state_results.append(final_result)
                compact_trace.append(_compact_state_trace(final_result))
                final_text = final_result.assistant_text or result.primary_text
                status = final_result.status
        return AgenticRunResult(
            final_text=final_text,
            visited_states=[result.state_id for result in state_results],
            state_results=state_results,
            status=status,
            pending_process_hints=pending_hints,
            compact_trace=compact_trace,
            metadata={
                "user_visible_owner": owner_state.value,
                "completed_process": "memory_ingestion_precheck",
            },
        )


def _query_context_from_handoff(
    conversation_context: ConversationContext,
    arguments: dict[str, Any],
    history_service: AgenticHistoryService,
) -> QueryRetrievalPlanningContext:
    metadata = dict(arguments.get("metadata") or {})
    seed_id = arguments.get("seed_id")
    if seed_id:
        metadata["seed_id"] = seed_id
    return QueryRetrievalPlanningContext(
        question=arguments.get("question")
        or conversation_context.current_message.content
        or "",
        conversation=history_service.child_conversation_context(conversation_context),
        desired_view=arguments.get("desired_view"),
        metadata=metadata,
    )


def _correction_context_from_handoff(
    conversation_context: ConversationContext,
    arguments: dict[str, Any],
    history_service: AgenticHistoryService,
) -> CorrectionIntakeContext:
    target_id = arguments.get("target_id")
    return CorrectionIntakeContext(
        correction_text=arguments.get("correction_text")
        or conversation_context.current_message.content
        or "",
        conversation=history_service.child_conversation_context(conversation_context),
        target_hints=[target_id] if target_id else [],
        metadata=dict(arguments.get("metadata") or {}),
    )


def _contradiction_context_from_handoff(arguments: dict[str, Any]) -> ContradictionReviewContext:
    return ContradictionReviewContext(
        proposed_write_ref=arguments.get("proposed_write_ref"),
        proposed_write=dict(arguments.get("proposed_write") or {}),
        affected_entity_refs=list(arguments.get("affected_entity_refs") or []),
        affected_relationship_refs=list(arguments.get("affected_relationship_refs") or []),
        source_refs=list(arguments.get("source_refs") or []),
        agent_doubt=arguments.get("agent_doubt") or "The agent requested contradiction review.",
        metadata=dict(arguments.get("metadata") or {}),
    )


def _last_handoff(events: list[AgenticToolEvent]) -> tuple[str | None, dict[str, Any]]:
    for event in reversed(events):
        data = event.data or {}
        target = data.get("handoff_target")
        if isinstance(target, str) and target:
            arguments = data.get("handoff_arguments")
            return target, arguments if isinstance(arguments, dict) else {}
    return None, {}


def _pending_process_hints(
    state_results: list[AgenticStateRunResult],
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for result in state_results:
        for event in result.tool_events:
            data = event.data or {}
            if "pending_process" in data:
                hints.append(data["pending_process"])
            result_payload = data.get("result")
            if isinstance(result_payload, dict) and result_payload.get("pending_process"):
                hints.append(result_payload["pending_process"])
    return hints


def _contradiction_pending_process_hints(
    state_result: AgenticStateRunResult,
) -> list[dict[str, Any]]:
    output = state_result.structured_output or {}
    if output.get("intent") != "needs_clarification":
        return []
    question = str(output.get("clarification_question") or "").strip()
    if not question:
        return []
    return [
        {
            "process_id": new_uuid(),
            "kind": "memory_ingestion",
            "status": "pending",
            "question": question,
            "metadata": {
                "source": "contradiction_review",
                "state_id": AgenticStateId.CONTRADICTION_REVIEW.value,
                "judge_request_id": output.get("judge_request_id"),
                "judge_decision_id": output.get("judge_decision_id"),
                "intent": output.get("intent"),
                "decision": output.get("decision"),
                "severity": output.get("severity"),
                "affected_refs": output.get("affected_refs") or [],
                "source_refs": output.get("source_refs") or [],
                "resume_context": output.get("resume_context") or {},
            },
        }
    ]


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


def _requires_direct_user_visibility(
    state_result: AgenticStateRunResult,
    state_results: list[AgenticStateRunResult],
) -> bool:
    if _pending_process_hints(state_results):
        return True
    for event in state_result.tool_events:
        data = event.data or {}
        if data.get("operation") == "request_user_confirmation":
            return True
        if "confirmation" in data:
            return True
        if "pending_process" in data:
            return True
    return False


def _compact_state_trace(state_result: AgenticStateRunResult) -> dict[str, Any]:
    return {
        "state_id": _state_value(state_result.state_id),
        "status": state_result.status,
        "assistant_text": state_result.assistant_text,
        "structured_output": state_result.structured_output,
        "handoff_target": state_result.handoff_target,
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
    for field_name in ("summary", "reason", "question"):
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
