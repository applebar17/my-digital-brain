from __future__ import annotations

from pydantic import Field

from my_digital_brain.agentic.base import AgenticModel
from my_digital_brain.agentic.contexts import ConversationContext
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.messages import NeutralConversationMessage, ToolCall


class AgenticRoute(AgenticModel):
    entry_state: AgenticStateId
    tool_call: ToolCall | None = None
    assistant_message: NeutralConversationMessage | None = None
    reason: str
    metadata: dict[str, str] = Field(default_factory=dict)


class DeterministicAgenticRouter:
    """Simple fallback router for Wave 1 contracts and tests.

    Real provider-backed routing can be added after the state, context, and
    prompt contracts are stable.
    """

    def route(self, context: ConversationContext) -> AgenticRoute:
        return self._route_conversation_entry(context)

    def select_entry_state(self, context: ConversationContext) -> AgenticStateId:
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
                reason="Cancellation is not model-visible in conversation entry.",
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

    def _tool_route(
        self,
        context: ConversationContext,
        *,
        tool_name: str,
        arguments: dict[str, str],
        reason: str,
    ) -> AgenticRoute:
        return AgenticRoute(
            entry_state=self.select_entry_state(context),
            tool_call=ToolCall(name=tool_name, arguments=arguments),
            reason=reason,
        )

    def _assistant_route(
        self,
        context: ConversationContext,
        message: str,
        *,
        reason: str,
    ) -> AgenticRoute:
        return AgenticRoute(
            entry_state=self.select_entry_state(context),
            assistant_message=NeutralConversationMessage.assistant(message),
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
