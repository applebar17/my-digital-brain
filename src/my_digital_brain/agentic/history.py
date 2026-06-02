from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from my_digital_brain.agentic.contexts import (
    ChannelSessionMetadata,
    ConversationContext,
    PendingProcessContext,
    PlanningContext,
    ToolResultContext,
)
from my_digital_brain.agentic.enums import (
    AgenticStateId,
    NeutralMessageKind,
    ToolResultStatus,
)
from my_digital_brain.agentic.messages import NeutralConversationMessage
from my_digital_brain.agentic.runtime_models import AgenticStateRunResult, AgenticToolEvent
from my_digital_brain.core.ids import new_uuid


BACKEND_ONLY_KEYS = {
    "channel_metadata",
    "backend_facade",
    "graph_service",
    "ingestion_service",
    "chat_store",
}


@dataclass(slots=True)
class HistoryProjectionPolicy:
    """Central policy for model-facing history and tool trace projections."""

    max_history_messages: int = 30
    compacted_summary_chars: int = 1200
    tool_data_chars: int = 4000


class AgenticHistoryService:
    """Build state-aware history payloads for agentic and LLM-backed processes.

    The service separates internal conversation state from model-facing
    projections. It preserves neutral history objects internally, removes
    backend-only channel/session metadata from prompts, and compacts nested tool
    activity before it is passed upward to later states.
    """

    def __init__(self, policy: HistoryProjectionPolicy | None = None) -> None:
        self.policy = policy or HistoryProjectionPolicy()

    def build_conversation_context(
        self,
        *,
        current_text: str,
        history_records: Iterable[Any] = (),
        current_time: datetime | None = None,
        timezone: str = "UTC",
        pending_process: PendingProcessContext | None = None,
        channel_metadata: ChannelSessionMetadata | None = None,
        compacted_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        fallback_current_text: str = "Message",
        exclude_record_ids: set[str] | None = None,
    ) -> ConversationContext:
        history = [
            message
            for message in (
                self.neutral_message_from_record(record)
                for record in history_records
                if not self._record_is_excluded(record, exclude_record_ids or set())
            )
            if message is not None
        ]
        compacted_summary, history = self.compact_history(
            history,
            compacted_summary=compacted_summary,
        )
        return ConversationContext(
            current_message=NeutralConversationMessage.user(
                current_text.strip() or fallback_current_text,
            ),
            history=history,
            compacted_summary=compacted_summary,
            current_time=current_time or _utc_now(),
            timezone=timezone,
            pending_process=pending_process,
            channel_metadata=channel_metadata,
            metadata=metadata or {},
        )

    def source_conversation_context(
        self,
        *,
        source_text: str,
        current_time: datetime | None = None,
        timezone: str = "UTC",
        pending_process: PendingProcessContext | None = None,
        history: list[NeutralConversationMessage] | None = None,
    ) -> ConversationContext:
        compacted_summary, compacted_history = self.compact_history(history or [])
        return ConversationContext(
            current_message=NeutralConversationMessage.user(
                source_text.strip() or "Memory source",
            ),
            history=compacted_history,
            compacted_summary=compacted_summary,
            current_time=current_time or _utc_now(),
            timezone=timezone,
            pending_process=pending_process,
        )

    def neutral_message_from_record(self, record: Any) -> NeutralConversationMessage | None:
        text = str(getattr(record, "text", "") or "").strip()
        if not text:
            return None
        role = _enum_value(getattr(record, "role", ""))
        message_id = str(getattr(record, "message_id", "") or "")
        created_at = getattr(record, "created_at", None)
        metadata = {
            key: value
            for key, value in {
                "channel_message_id": getattr(record, "channel_message_id", None),
                "pending_process_id": getattr(record, "pending_process_id", None),
                "source_ref": getattr(record, "source_ref", None),
            }.items()
            if value is not None
        }
        if role == "user":
            kind = NeutralMessageKind.USER
        elif role == "assistant":
            kind = NeutralMessageKind.ASSISTANT
        else:
            kind = NeutralMessageKind.COMPACTED_SUMMARY
        payload: dict[str, Any] = {
            "kind": kind,
            "content": text,
            "created_at": created_at or _utc_now(),
            "metadata": metadata,
        }
        if message_id:
            payload["message_id"] = message_id
        return NeutralConversationMessage(**payload)

    def compact_history(
        self,
        history: list[NeutralConversationMessage],
        *,
        compacted_summary: str | None = None,
    ) -> tuple[str | None, list[NeutralConversationMessage]]:
        if len(history) <= self.policy.max_history_messages:
            return compacted_summary, history

        dropped = history[: -self.policy.max_history_messages]
        kept = history[-self.policy.max_history_messages :]
        deterministic_summary = self._summarize_messages(dropped)
        summary = "\n".join(
            item for item in [compacted_summary, deterministic_summary] if item
        )
        return _truncate(summary, self.policy.compacted_summary_chars), kept

    def child_conversation_context(self, conversation: ConversationContext) -> ConversationContext:
        """Return a specialist-state copy without backend-only channel metadata."""

        compacted_summary, history = self.compact_history(
            list(conversation.history),
            compacted_summary=conversation.compacted_summary,
        )
        return conversation.model_copy(
            update={
                "history": history,
                "compacted_summary": compacted_summary,
                "channel_metadata": None,
            },
            deep=True,
        )

    def model_payload_for_state(self, state_id: AgenticStateId | str, payload: Any) -> Any:
        state = AgenticStateId(state_id)
        if isinstance(payload, ConversationContext):
            projected = payload.model_copy(deep=True)
            if state not in {
                AgenticStateId.CONVERSATION_ENTRY,
                AgenticStateId.PENDING_PROCESS_REVIEW,
            }:
                projected = self.child_conversation_context(projected)
            return self._model_payload(projected)
        return self._model_payload(payload)

    def tool_result_contexts_from_events(
        self,
        events: Iterable[AgenticToolEvent],
        *,
        skip_handoff_targets: set[str] | None = None,
    ) -> list[ToolResultContext]:
        skipped = skip_handoff_targets or set()
        results: list[ToolResultContext] = []
        for event in events:
            data = event.data or {}
            handoff_target = data.get("handoff_target")
            if isinstance(handoff_target, str) and handoff_target in skipped:
                continue
            results.append(
                ToolResultContext(
                    tool_name=event.tool_name,
                    status=(
                        ToolResultStatus.FAILED
                        if event.status != ToolResultStatus.OK.value
                        else ToolResultStatus.OK
                    ),
                    summary=self.tool_event_summary(event),
                    data=self._compact_tool_data(
                        {
                            **data,
                            **({"error": event.error} if event.error else {}),
                        },
                    ),
                ),
            )
        return results

    def append_tool_events_to_planning_context(
        self,
        planning_context: PlanningContext,
        state_result: AgenticStateRunResult,
        *,
        skip_handoff_targets: set[str] | None = None,
    ) -> None:
        planning_context.prior_tool_outputs.extend(
            self.tool_result_contexts_from_events(
                state_result.tool_events,
                skip_handoff_targets=skip_handoff_targets,
            ),
        )

    def owner_finalization_context(
        self,
        conversation: ConversationContext,
        *,
        completed_state: AgenticStateRunResult,
    ) -> ConversationContext:
        return self.owner_finalization_context_from_output(
            conversation,
            process_name=_enum_value(completed_state.state_id),
            summary=self.state_result_summary(completed_state),
            data=completed_state.model_dump(mode="json", exclude_none=True),
        )

    def owner_finalization_context_from_output(
        self,
        conversation: ConversationContext,
        *,
        process_name: str,
        summary: str,
        data: dict[str, Any] | None = None,
    ) -> ConversationContext:
        compact_output = NeutralConversationMessage.tool_output_message(
            tool_call_id=new_uuid(),
            name=process_name,
            status=ToolResultStatus.OK,
            content=summary,
            data=self._compact_tool_data(data or {"summary": summary}),
            owner_visible=False,
        )
        compacted_summary, history = self.compact_history(
            [*conversation.history, compact_output],
            compacted_summary=conversation.compacted_summary,
        )
        return conversation.model_copy(
            update={
                "history": history,
                "compacted_summary": compacted_summary,
                "channel_metadata": None,
                "metadata": {
                    **conversation.metadata,
                    "owner_finalization": True,
                    "completed_process": process_name,
                    "compact_process_output": summary,
                },
            },
            deep=True,
        )

    def state_result_summary(self, state_result: AgenticStateRunResult) -> str:
        if state_result.assistant_text:
            return state_result.assistant_text
        for event in reversed(state_result.tool_events):
            summary = self.tool_event_summary(event)
            if summary:
                return summary
        return f"{_enum_value(state_result.state_id)} completed."

    def tool_event_summary(self, event: AgenticToolEvent) -> str:
        if event.output:
            return event.output
        error = event.error or {}
        message = error.get("message")
        hint = error.get("hint")
        if message and hint:
            return f"{message} Hint: {hint}"
        if message:
            return str(message)
        return f"{event.tool_name} completed with status {event.status}."

    def _model_payload(self, payload: Any) -> Any:
        if hasattr(payload, "model_facing_payload"):
            dumped = payload.model_facing_payload()
        elif hasattr(payload, "model_dump"):
            dumped = payload.model_dump(mode="json", exclude_none=True)
        else:
            dumped = payload
        return self._drop_backend_only_keys(dumped)

    def _drop_backend_only_keys(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._drop_backend_only_keys(item)
                for key, item in value.items()
                if key not in BACKEND_ONLY_KEYS
            }
        if isinstance(value, list):
            return [self._drop_backend_only_keys(item) for item in value]
        return value

    def _compact_tool_data(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            serialized = json.dumps(data, ensure_ascii=True, sort_keys=True, default=str)
        except TypeError:
            return {"summary": str(data), "truncated": True}
        if len(serialized) <= self.policy.tool_data_chars:
            return data
        return {
            "summary": _truncate(serialized, self.policy.tool_data_chars),
            "truncated": True,
        }

    def _summarize_messages(self, messages: list[NeutralConversationMessage]) -> str:
        parts: list[str] = []
        for message in messages[-10:]:
            label = _enum_value(message.kind)
            content = message.content
            if message.tool_call is not None:
                content = f"tool_call {message.tool_call.name}"
            if message.tool_output is not None:
                content = f"tool_output {message.tool_output.name}: {message.tool_output.content}"
            if content:
                parts.append(f"{label}: {content}")
        return "Earlier conversation summary: " + " | ".join(parts)

    @staticmethod
    def _record_is_excluded(record: Any, excluded_ids: set[str]) -> bool:
        if not excluded_ids:
            return False
        values = {
            str(getattr(record, "message_id", "") or ""),
            str(getattr(record, "channel_message_id", "") or ""),
        }
        return bool(values.intersection(excluded_ids))


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)] + "..."


def _utc_now() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
