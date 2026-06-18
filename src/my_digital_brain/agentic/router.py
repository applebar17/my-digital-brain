from __future__ import annotations

from pydantic import Field

from my_digital_brain.agentic.base import AgenticModel
from my_digital_brain.agentic.contexts import ConversationContext
from my_digital_brain.agentic.enums import AgenticStateId, PendingMessageIntent
from my_digital_brain.agentic.messages import NeutralConversationMessage, ToolCall


class AgenticRoute(AgenticModel):
    entry_state: AgenticStateId
    tool_call: ToolCall | None = None
    assistant_message: NeutralConversationMessage | None = None
    pending_intent: PendingMessageIntent | None = None
    reason: str
    metadata: dict[str, str] = Field(default_factory=dict)


class DeterministicAgenticRouter:
    """Simple fallback router for Wave 1 contracts and tests.

    Real provider-backed routing can be added after the state, context, and
    prompt contracts are stable.
    """

    def route(self, context: ConversationContext) -> AgenticRoute:
        if self._selected_pending_process(context) is not None:
            return self._route_pending_process_review(context)
        return self._route_conversation_entry(context)

    def select_entry_state(self, context: ConversationContext) -> AgenticStateId:
        if self._selected_pending_process(context) is not None:
            return AgenticStateId.PENDING_PROCESS_REVIEW
        return AgenticStateId.CONVERSATION_ENTRY

    def _route_conversation_entry(self, context: ConversationContext) -> AgenticRoute:
        text = (context.current_message.content or "").strip()
        lower_text = text.lower()

        if self._is_status(lower_text):
            return self._assistant_route(
                context,
                "Status is handled by the chat runtime control layer, not by the conversation entry state.",
                reason="Status shortcut is not a conversation-entry model-visible tool.",
            )
        if self._is_cancel(lower_text):
            return self._assistant_route(
                context,
                "There is no active pending process to cancel.",
                reason="Cancellation is only model-visible during pending process review.",
            )
        if lower_text.startswith("/ask"):
            return self._tool_route(
                context,
                tool_name="query_memory_context",
                arguments={"question": self._command_payload(text, "/ask") or text},
                reason="Explicit memory query command.",
            )
        if lower_text.startswith("/correct"):
            return self._tool_route(
                context,
                tool_name="update_memory_graph",
                arguments={
                    "source_text": self._command_payload(text, "/correct") or text,
                    "guidelines": "Apply this as a correction or update to the memory graph.",
                    "desired_work": "correct_or_update_memory_graph",
                },
                reason="Explicit graph update/correction command.",
            )

        return self._assistant_route(
            context,
            "Provider-backed conversation routing is required to decide whether this "
            "message should be answered, stored, queried, or corrected.",
            reason="Deterministic fallback does not infer a default memory action.",
        )

    def _route_pending_process_review(self, context: ConversationContext) -> AgenticRoute:
        text = (context.current_message.content or "").strip()
        lower_text = text.lower()
        pending_process = self._selected_pending_process(context)
        if pending_process is None:
            return self._assistant_route(
                context,
                "There is no pending process to review.",
                reason="Pending process review was requested without pending context.",
            )

        if self._is_cancel(lower_text):
            return self._tool_route(
                context,
                tool_name="cancel_pending_process",
                arguments={
                    "pending_process_id": pending_process.process_id,
                    "reason": self._command_payload(text, "/cancel"),
                },
                reason="Explicit cancellation while pending process is active.",
                pending_intent=PendingMessageIntent.CANCEL,
            )
        if self._is_pause(lower_text):
            return self._tool_route(
                context,
                tool_name="pause_pending_process",
                arguments={
                    "pending_process_id": pending_process.process_id,
                    "reason": text,
                },
                reason="User does not want or cannot complete the pending process now.",
                pending_intent=PendingMessageIntent.PAUSE,
            )
        if lower_text.startswith("/ask"):
            return self._tool_route(
                context,
                tool_name="query_memory_context",
                arguments={
                    "question": self._command_payload(text, "/ask") or text,
                    "pending_process_policy": "pause",
                },
                reason="User asked a new question while a process is pending.",
                pending_intent=PendingMessageIntent.QUESTION,
            )
        if lower_text.startswith("/correct"):
            return self._tool_route(
                context,
                tool_name="update_memory_graph",
                arguments={
                    "source_text": self._command_payload(text, "/correct") or text,
                    "guidelines": "Apply this as a correction or update to the memory graph.",
                    "desired_work": "correct_or_update_memory_graph",
                    "pending_process_policy": "pause",
                },
                reason="User proposed a graph update/correction while a process is pending.",
                pending_intent=PendingMessageIntent.CORRECTION,
            )
        if lower_text.startswith("/memory") or lower_text.startswith("/new"):
            return self._tool_route(
                context,
                tool_name="start_memory_ingestion",
                arguments={
                    "source_text": self._command_payload(text, lower_text.split(maxsplit=1)[0])
                    or text,
                    "pending_process_policy": "pause",
                },
                reason="User explicitly started a different memory while pending.",
                pending_intent=PendingMessageIntent.NEW_MEMORY,
            )

        return self._assistant_route(
            context,
            "Provider-backed pending process review is required to decide whether this "
            "message resumes, pauses, cancels, or bypasses the pending process.",
            reason="Deterministic fallback does not infer pending-process intent.",
        )

    def _tool_route(
        self,
        context: ConversationContext,
        *,
        tool_name: str,
        arguments: dict[str, str],
        reason: str,
        pending_intent: PendingMessageIntent | None = None,
    ) -> AgenticRoute:
        return AgenticRoute(
            entry_state=self.select_entry_state(context),
            tool_call=ToolCall(name=tool_name, arguments=arguments),
            pending_intent=pending_intent,
            reason=reason,
        )

    def _assistant_route(
        self,
        context: ConversationContext,
        message: str,
        *,
        reason: str,
        pending_intent: PendingMessageIntent | None = None,
    ) -> AgenticRoute:
        return AgenticRoute(
            entry_state=self.select_entry_state(context),
            assistant_message=NeutralConversationMessage.assistant(message),
            pending_intent=pending_intent,
            reason=reason,
        )

    def _is_status(self, lower_text: str) -> bool:
        return lower_text == "/status" or lower_text.startswith("/status ")

    def _is_cancel(self, lower_text: str) -> bool:
        return lower_text in {"/cancel", "cancel", "skip"} or lower_text.startswith("/cancel ")

    def _is_pause(self, lower_text: str) -> bool:
        return lower_text in {
            "i don't remember",
            "i do not remember",
            "don't remember",
            "do not remember",
            "i don't know",
            "i do not know",
            "non lo so",
            "pause",
        }

    def _command_payload(self, text: str, command: str) -> str:
        if not text.lower().startswith(command):
            return ""
        return text[len(command) :].strip()

    def _selected_pending_process(self, context: ConversationContext):
        if context.pending_process is not None:
            return context.pending_process
        if context.pending_processes:
            return context.pending_processes[0]
        return None
