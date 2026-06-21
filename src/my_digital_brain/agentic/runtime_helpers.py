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
