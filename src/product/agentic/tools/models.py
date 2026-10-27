"""Backend-only contracts for invoking registered tools from agentic states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from product.ai.ai_clients.protocols.protocol_chat import Msg

if TYPE_CHECKING:
    from product.agentic.history import AgenticHistorySession


@dataclass(frozen=True)
class AgenticToolInvocationContext:
    """Bind one provider tool call to its parent state and shared history session."""

    history_session: AgenticHistorySession
    parent_state_run_id: str
    parent_provider_call_id: str

    def inherited_history(self) -> list[Msg]:
        """Return the framework-owned default history projection for a child state."""
        return self.history_session.history_for_child(self.parent_state_run_id)
