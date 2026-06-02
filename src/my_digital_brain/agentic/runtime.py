from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from my_digital_brain.agentic.contexts import (
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
from my_digital_brain.ai.schemas import AIRequestContext, ChatMessage, ChatRequest
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.core.ids import new_uuid
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
                            "context": self.history_service.model_payload_for_state(
                                state_id,
                                invocation.context_payload,
                            ),
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
        has_error = any(event.status != "ok" for event in tool_events)
        return AgenticStateRunResult(
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


@dataclass(slots=True)
class AgenticRuntime:
    state_runner: AgenticStateRunner
    max_state_transitions: int = 5

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
                pending_process_hints=[
                    *_pending_process_hints(state_results),
                    *_implicit_pending_process_hints(state_result),
                ],
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

    def _entry_state(self, conversation_context: ConversationContext) -> AgenticStateId:
        if conversation_context.pending_process is not None:
            return AgenticStateId.PENDING_PROCESS_REVIEW
        return AgenticStateId.CONVERSATION_ENTRY

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


def _implicit_pending_process_hints(
    state_result: AgenticStateRunResult,
) -> list[dict[str, Any]]:
    if state_result.state_id != AgenticStateId.CONTRADICTION_REVIEW:
        return []
    text = (state_result.assistant_text or "").strip()
    if not text or "?" not in text:
        return []
    return [
        {
            "process_id": new_uuid(),
            "kind": "memory_ingestion",
            "status": "pending",
            "question": text,
            "metadata": {
                "source": "contradiction_review",
                "state_id": AgenticStateId.CONTRADICTION_REVIEW.value,
            },
        }
    ]


def _requires_direct_user_visibility(
    state_result: AgenticStateRunResult,
    state_results: list[AgenticStateRunResult],
) -> bool:
    if _pending_process_hints(state_results) or _implicit_pending_process_hints(state_result):
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
