from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic.contexts import (
    ContradictionJudgeResultContext,
    ConversationContext,
    MemoryPlan,
)
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.runtime_models import (
    AgenticRunResult,
    AgenticStateRunResult,
)
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ai.schemas import ChatMessage
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.debug import AIFlowTraceSection


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


def _memory_ingestion_error_result(
    state_results: list[AgenticStateRunResult],
    compact_trace: list[dict[str, Any]],
    failed_result: AgenticStateRunResult,
) -> AgenticRunResult:
    return AgenticRunResult(
        final_text=failed_result.assistant_text,
        visited_states=[result.state_id for result in state_results],
        state_results=state_results,
        status="error",
        compact_trace=compact_trace,
    )


def _memory_ingestion_clarification_result(
    action: Any,
    execution_context: AgenticToolExecutionContext,
    conversation_context: ConversationContext,
) -> AgenticRunResult:
    from my_digital_brain.chat.clarification import build_clarification_packet

    frame_id = execution_context.frame_id or new_uuid()
    execution_context.frame_id = frame_id
    clarification_tool_call_id = f"clarification-{new_uuid()}"
    questions = action.payload.get("questions") or []
    if not questions:
        questions = [
            {
                "question": action.rationale or "What should I clarify before continuing?",
                "free_text_allowed": True,
                "required": True,
                "selection_mode": "single",
            }
        ]
    packet = build_clarification_packet(
        frame_id=frame_id,
        origin_state_id=AgenticStateId.MEMORY_INGESTION.value,
        reason=action.rationale or "Memory ingestion needs clarification.",
        questions=questions,
        tool_call_id=clarification_tool_call_id,
        tool_name="request_user_clarification",
        target_refs=action.target_refs,
    )
    interruption = {
        "frame_id": frame_id,
        "state_id": AgenticStateId.MEMORY_INGESTION.value,
        "tool_call_id": clarification_tool_call_id,
        "tool_name": "request_user_clarification",
        "clarification_packet": packet.model_dump(mode="json", exclude_none=True),
    }
    if execution_context.chat_store is not None:
        from my_digital_brain.chat.models import AgenticFrame

        frame = AgenticFrame(
            frame_id=frame_id,
            session_id=execution_context.session_id or conversation_context.context_id,
            state_id=AgenticStateId.MEMORY_INGESTION.value,
            status="interrupted",
            messages=[
                {
                    "role": "user",
                    "content": conversation_context.current_message.content or "Clarification needed.",
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": clarification_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": "request_user_clarification",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
            ],
            context_payload=_frame_context_payload(None, conversation_context),
            compact_trace=[],
            parent_frame_id=execution_context.parent_frame_id,
            parent_tool_call_id=execution_context.parent_tool_call_id,
            active_tool_call_id=clarification_tool_call_id,
            active_tool_name="request_user_clarification",
            clarification_packet=packet,
            metadata={
                "interrupted_state": AgenticStateId.MEMORY_INGESTION.value,
                "tool_call_id": clarification_tool_call_id,
                "tool_name": "request_user_clarification",
            },
        )
        execution_context.chat_store.save_agentic_frame(frame.session_id, frame)
    state_result = AgenticStateRunResult(
        state_id=AgenticStateId.MEMORY_INGESTION,
        assistant_text=packet.questions[0].question,
        terminal=False,
        status="interrupted",
        metadata={"interruption": interruption},
    )
    return AgenticRunResult(
        final_text=state_result.assistant_text,
        visited_states=[state_result.state_id],
        state_results=[state_result],
        status="interrupted",
        interruption=interruption,
        compact_trace=[_compact_state_trace(state_result)],
        metadata={"user_visible_owner": AgenticStateId.MEMORY_INGESTION.value},
    )


def _collect_memory_plan_refs(plan: MemoryPlan, key: str) -> list[str]:
    values: list[str] = []
    for step in plan.steps:
        for action in step.actions:
            candidate = action.payload.get(key)
            if isinstance(candidate, list):
                values.extend(str(item) for item in candidate)
    return list(dict.fromkeys(values))


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
