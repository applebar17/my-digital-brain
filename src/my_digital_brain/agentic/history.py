from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from my_digital_brain.agentic.contexts import (
    ChannelSessionMetadata,
    ConversationContext,
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
from my_digital_brain.ai.schemas import ChatMessage
from my_digital_brain.core.ids import new_uuid

BACKEND_ONLY_KEYS = {
    "channel_metadata",
    "graph_service",
    "ingestion_service",
    "chat_store",
}

PROMPT_CONTEXT_EXCLUDED_KEYS = {
    "channel_metadata",
    "conversation",
    "current_message",
    "history",
    "model_user_message",
    "raw_text",
    "source_text",
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
            channel_metadata=channel_metadata,
            metadata=metadata or {},
        )

    def source_conversation_context(
        self,
        *,
        source_text: str,
        current_time: datetime | None = None,
        timezone: str = "UTC",
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
        summary = "\n".join(item for item in [compacted_summary, deterministic_summary] if item)
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

    def promote_messages_to_master_history(
        self,
        master_history: Iterable[dict[str, Any]],
        messages: Iterable[Any],
    ) -> list[dict[str, Any]]:
        """Append selected messages to the chat-wide internal history.

        Callers choose which completed process messages are important enough to
        promote. The active LLM session transcript remains separate.
        """

        promoted = [dict(message) for message in master_history if isinstance(message, dict)]
        promoted.extend(
            message
            for message in (self._master_history_message(item) for item in messages)
            if message is not None
        )
        return promoted

    def append_user_message_to_master_history(
        self,
        master_history: Iterable[dict[str, Any]],
        content: str,
    ) -> list[dict[str, Any]]:
        """Ensure a source/user message exists once in master history."""

        normalized = content.strip()
        history = [dict(message) for message in master_history if isinstance(message, dict)]
        if not normalized:
            return history
        if any(
            str(message.get("role") or "") == "user"
            and str(message.get("content") or "").strip() == normalized
            for message in history
        ):
            return history
        history.append({"role": "user", "content": normalized})
        return history

    def promote_clarification_to_master_history(
        self,
        master_history: Iterable[dict[str, Any]],
        packet: Any,
        answer_messages: Iterable[Any] = (),
    ) -> list[dict[str, Any]]:
        """Promote a clarification exchange without UI answer choices."""

        question_messages = [
            {"role": "assistant", "content": question_text}
            for question in getattr(packet, "questions", ())
            if (question_text := str(getattr(question, "question", "") or "").strip())
        ]
        return self.promote_messages_to_master_history(
            master_history,
            [*question_messages, *answer_messages],
        )

    def model_payload_for_state(self, state_id: AgenticStateId | str, payload: Any) -> Any:
        state = AgenticStateId(state_id)
        if isinstance(payload, ConversationContext):
            projected = payload.model_copy(deep=True)
            if state != AgenticStateId.CONVERSATION_ENTRY:
                projected = self.child_conversation_context(projected)
            return self._model_payload(projected)
        return self._model_payload(payload)

    def model_prompt_context_for_state(
        self,
        state_id: AgenticStateId | str,
        payload: Any,
    ) -> Any:
        """Return process context for system-prompt sections, not chat messages."""

        if hasattr(payload, "system_prompt_payload"):
            projected = payload.system_prompt_payload()
            projected = self._drop_backend_only_keys(projected)
        else:
            projected = self.model_payload_for_state(state_id, payload)
        return self._drop_prompt_context_message_keys(projected)

    def model_messages_for_state(
        self,
        state_id: AgenticStateId | str,
        payload: Any,
        *,
        current_text: str | None = None,
    ) -> list[ChatMessage]:
        """Render role-preserved conversation messages for a model call."""

        state = AgenticStateId(state_id)
        transient_messages = self.transient_user_messages_from_payload(payload)
        conversation = self._conversation_for_messages(state, payload)
        if conversation is not None:
            return [
                *self._chat_messages_from_conversation(conversation),
                *transient_messages,
            ]
        source_text = self._source_text_from_payload(payload) or current_text
        messages: list[ChatMessage] = []
        if source_text and source_text.strip():
            messages.append(ChatMessage(role="user", content=source_text.strip()))
        messages.extend(transient_messages)
        return messages

    def ingestion_messages_for_source(
        self,
        source: Any,
        *,
        appended_user_message: str | None = None,
    ) -> list[ChatMessage]:
        """Render source-backed ingestion messages plus a transient user message."""

        messages = self._messages_from_source_metadata(source)
        source_text = self._source_text_from_source(source)
        if source_text and not any(
            message.role == "user" and message.content.strip() == source_text.strip()
            for message in messages
        ):
            insert_at = next(
                (
                    index
                    for index, message in enumerate(messages)
                    if _is_clarification_question(messages, index)
                ),
                len(messages),
            )
            messages.insert(insert_at, ChatMessage(role="user", content=source_text))
        if appended_user_message and appended_user_message.strip():
            messages.append(ChatMessage(role="user", content=appended_user_message.strip()))
        return messages

    def transient_user_messages_from_payload(self, payload: Any) -> list[ChatMessage]:
        message = self._transient_user_message_from_payload(payload)
        if message is None:
            return []
        return [ChatMessage(role="user", content=message)]

    def tool_result_contexts_from_events(
        self,
        events: Iterable[AgenticToolEvent],
    ) -> list[ToolResultContext]:
        results: list[ToolResultContext] = []
        for event in events:
            data = event.data or {}
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
    ) -> None:
        planning_context.prior_tool_outputs.extend(
            self.tool_result_contexts_from_events(
                state_result.tool_events,
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

    @staticmethod
    def _master_history_message(message: Any) -> dict[str, Any] | None:
        if hasattr(message, "model_dump"):
            message = message.model_dump(mode="json", exclude_none=True)
        if not isinstance(message, dict):
            return None
        role = str(message.get("role") or "").strip()
        content = message.get("content")
        if role not in {"user", "assistant", "developer", "tool"} or not content:
            return None
        return {"role": role, "content": str(content)}

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

    def _drop_prompt_context_message_keys(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._drop_prompt_context_message_keys(item)
                for key, item in value.items()
                if key not in PROMPT_CONTEXT_EXCLUDED_KEYS
            }
        if isinstance(value, list):
            return [self._drop_prompt_context_message_keys(item) for item in value]
        return value

    def _conversation_for_messages(
        self,
        state: AgenticStateId,
        payload: Any,
    ) -> ConversationContext | None:
        conversation: ConversationContext | None = None
        if isinstance(payload, ConversationContext):
            conversation = payload
        else:
            possible = getattr(payload, "conversation", None)
            if isinstance(possible, ConversationContext):
                conversation = possible
        if conversation is None:
            return None
        if state != AgenticStateId.CONVERSATION_ENTRY:
            return self.child_conversation_context(conversation)
        return conversation

    def _chat_messages_from_conversation(
        self,
        conversation: ConversationContext,
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        open_tool_call_ids: set[str] = set()
        for message in [*conversation.history, conversation.current_message]:
            rendered = self._chat_message_from_neutral(message, open_tool_call_ids)
            if rendered is not None:
                messages.append(rendered)
        return messages

    def _chat_message_from_neutral(
        self,
        message: NeutralConversationMessage,
        open_tool_call_ids: set[str],
    ) -> ChatMessage | None:
        if message.kind == NeutralMessageKind.USER:
            return ChatMessage(role="user", content=message.content or "")
        if message.kind == NeutralMessageKind.ASSISTANT:
            return ChatMessage(role="assistant", content=message.content or "")
        if message.kind == NeutralMessageKind.ASSISTANT_TOOL_CALL and message.tool_call:
            call = message.tool_call
            open_tool_call_ids.add(call.tool_call_id)
            return ChatMessage(
                role="assistant",
                content=message.content,
                tool_calls=[
                    {
                        "id": call.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(
                                call.arguments,
                                ensure_ascii=True,
                                sort_keys=True,
                                default=str,
                            ),
                        },
                    }
                ],
            )
        if message.kind == NeutralMessageKind.TOOL_OUTPUT and message.tool_output:
            output = message.tool_output
            if output.tool_call_id not in open_tool_call_ids:
                return None
            open_tool_call_ids.discard(output.tool_call_id)
            return ChatMessage(
                role="tool",
                tool_call_id=output.tool_call_id,
                content=output.content
                or json.dumps(
                    output.model_dump(mode="json", exclude_none=True),
                    ensure_ascii=True,
                    sort_keys=True,
                    default=str,
                ),
            )
        return None

    def _source_text_from_payload(self, payload: Any) -> str | None:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json", exclude_none=True)
        if isinstance(payload, dict):
            for key in (
                "source_text",
                "raw_text",
                "text",
                "question",
                "correction_text",
            ):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            for item in payload.values():
                found = self._source_text_from_payload(item)
                if found:
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = self._source_text_from_payload(item)
                if found:
                    return found
        return None

    def _transient_user_message_from_payload(self, payload: Any) -> str | None:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json", exclude_none=True)
        if isinstance(payload, dict):
            value = payload.get("model_user_message")
            if isinstance(value, str) and value.strip():
                return value.strip()
            for item in payload.values():
                found = self._transient_user_message_from_payload(item)
                if found:
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = self._transient_user_message_from_payload(item)
                if found:
                    return found
        return None

    def _messages_from_source_metadata(self, source: Any) -> list[ChatMessage]:
        metadata = getattr(source, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
        messages: list[ChatMessage] = []
        raw_history = metadata.get("model_facing_history")
        if isinstance(raw_history, list):
            for item in raw_history:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "").strip()
                content = item.get("content")
                if role in {"user", "assistant", "developer", "tool"} and content:
                    messages.append(ChatMessage(role=role, content=str(content)))
        clarifications = metadata.get("clarification_history")
        if isinstance(clarifications, list):
            for item in clarifications:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question") or "").strip()
                answer = str(item.get("answer") or "").strip()
                if question:
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content=f"Clarification requested: {question}",
                        ),
                    )
                if answer:
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=f"Clarification answer: {answer}",
                        ),
                    )
        return messages

    def _source_text_from_source(self, source: Any) -> str | None:
        for key in ("raw_text", "content_ref"):
            value = getattr(source, key, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

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


def _is_clarification_question(messages: list[ChatMessage], index: int) -> bool:
    message = messages[index]
    if message.role != "assistant":
        return False
    if message.content.startswith("Clarification"):
        return True
    if index + 1 >= len(messages):
        return False
    next_message = messages[index + 1]
    return next_message.role == "user" and next_message.content.startswith("Clarification answer:")


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)] + "..."


def _utc_now() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
