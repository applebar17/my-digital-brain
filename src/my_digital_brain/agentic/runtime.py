from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from my_digital_brain.agentic.contexts import (
    ContradictionJudgeResultContext,
    ContradictionReviewContext,
    ConversationContext,
    EdgeMemoryPlan,
    MemoryIngestionContext,
    MemoryIngestionReasoning,
    MemoryIngestionResultContext,
    MemoryLogMemoryPlan,
    MemoryPlan,
    NodeMemoryPlan,
)
from my_digital_brain.agentic.enums import AgenticStateId, MemoryPlanningPhase
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.planning_contracts import (
    PlanningPurposeGuidelines,
    PlanningTransformContext,
)
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
from my_digital_brain.agentic.runtime_helpers import (
    _chat_message_to_frame_dict,
    _collect_child_payload_values,
    _collect_memory_plan_refs,
    _compact_state_trace,
    _contradiction_runtime_status,
    _frame_context_payload,
    _memory_ingestion_error_result,
    _state_value,
    _structured_summary,
    _system_prompt_with_runtime_context,
    _trace_json_section,
)


from my_digital_brain.agentic.runtime_state import AgenticStateRunner
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

        if current_state == AgenticStateId.MEMORY_INGESTION and isinstance(
            current_payload, MemoryIngestionContext
        ):
            return self._run_memory_ingestion_planning(
                current_payload,
                execution_context,
                conversation_context,
            )

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

    def _run_memory_ingestion_planning(
        self,
        payload: MemoryIngestionContext,
        execution_context: AgenticToolExecutionContext,
        conversation_context: ConversationContext,
    ) -> AgenticRunResult:
        from my_digital_brain.agentic.runtime_memory import MemoryIngestionRuntimeService

        return MemoryIngestionRuntimeService(self).run(
            payload,
            execution_context,
            conversation_context,
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
            interrupted_child_frame_id = interruption.get("child_frame_id") or interruption.get("frame_id")
            interrupted_child_state_id = interruption.get("child_state_id") or interruption.get("state_id") or child_state.value
            return ToolResult(
                status="interrupted",
                output=result.final_text or "Child frame needs clarification.",
                data={
                    "operation": tool_name,
                    "interruption_owner": "child",
                    "parent_frame_id": parent_frame.get("frame_id"),
                    "child_frame_id": interrupted_child_frame_id,
                    "child_state_id": interrupted_child_state_id,
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
        resolved_clarifications = list(result.metadata.get("resolved_clarifications") or [])
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
                "resolved_clarifications": resolved_clarifications,
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
        active_tool_call_id = parent_execution_context.current_tool_call_id
        active_tool_name = parent_execution_context.current_tool_name or tool_name
        active_tool_arguments = dict(parent_execution_context.current_tool_arguments)
        if not messages:
            active_tool_call_id = active_tool_call_id or f"child-{new_uuid()}"
            messages = [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": active_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": active_tool_name,
                                "arguments": json.dumps(
                                    active_tool_arguments,
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
        interrupted_child_frame_id = child_interruption.get("child_frame_id") or child_interruption.get("frame_id")
        interrupted_child_state_id = child_interruption.get("child_state_id") or child_interruption.get("state_id")
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
            active_tool_call_id=active_tool_call_id,
            active_tool_name=active_tool_name,
            metadata={
                "waiting_for_child_frame_id": interrupted_child_frame_id,
                "waiting_for_child_state_id": interrupted_child_state_id,
                "child_tool_call_id": child_interruption.get("tool_call_id"),
                "child_tool_name": child_interruption.get("tool_name"),
            },
        )
        parent_execution_context.chat_store.save_agentic_frame(frame.session_id, frame)
        if interrupted_child_frame_id:
            try:
                child_frame = parent_execution_context.chat_store.get_agentic_frame(str(interrupted_child_frame_id))
                if not child_frame.parent_tool_call_id:
                    parent_execution_context.chat_store.save_agentic_frame(
                        child_frame.session_id,
                        child_frame.model_copy(
                            update={
                                "parent_frame_id": frame.frame_id,
                                "parent_tool_call_id": active_tool_call_id,
                            },
                            deep=True,
                        ),
                    )
            except Exception:
                pass
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
        resolved_clarifications: list[dict[str, Any]] | None = None,
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
        if resolved_clarifications is None and frame.clarification_packet is not None:
            from my_digital_brain.chat.clarification import resolved_clarifications_from_answers

            resolved_clarifications = resolved_clarifications_from_answers(
                frame.clarification_packet,
                answer_packet,
            )
        resolved_clarifications = list(resolved_clarifications or frame.metadata.get("resolved_clarifications") or [])
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
                "resolved_clarifications": resolved_clarifications,
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
            metadata={"resumed_frame_id": frame.frame_id, "resolved_clarifications": resolved_clarifications},
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
            metadata={"resumed_frame_id": frame.frame_id, "resolved_clarifications": resolved_clarifications},
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
        resolved_clarifications = list(child_frame.metadata.get("resolved_clarifications") or child_result.metadata.get("resolved_clarifications") or [])
        tool_result = ToolResult(
            status="ok" if child_result.status == "ok" else child_result.status,
            output=summary,
            data={
                "operation": parent.active_tool_name or child_frame.state_id,
                "child_frame_id": child_frame.frame_id,
                "child_state_id": child_frame.state_id,
                "summary": summary,
                "child_status": child_result.status,
                "resolved_clarifications": resolved_clarifications,
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
            metadata={"resumed_child_frame_id": child_frame.frame_id, "resolved_clarifications": resolved_clarifications},
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
                "resolved_clarifications": resolved_clarifications,
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
                **frame.metadata,
                "completed_state_status": state_result.status,
                "summary": self.state_runner.history_service.state_result_summary(state_result),
                **(
                    {"resolved_clarifications": state_result.metadata["resolved_clarifications"]}
                    if state_result.metadata.get("resolved_clarifications") is not None
                    else {}
                ),
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
