"""Own one orchestration's shared history and isolated state transcripts."""

from copy import deepcopy
from uuid import uuid4

from product.agentic.contracts import MasterHistoryPromotion, StateHistory
from product.ai.ai_clients.protocols.protocol_chat import Msg


class AgenticHistorySession:
    """Manage shared history revisions and active state-local transcripts."""

    def __init__(self, master_history: list[Msg] | None = None) -> None:
        """Copy caller-loaded conversation messages into this session's ownership."""
        self._master_history = deepcopy(master_history or [])
        self._master_revision = 0
        self._state_histories: dict[str, StateHistory] = {}
        self._promotions: list[MasterHistoryPromotion] = []

    @property
    def master_revision(self) -> int:
        """Return the current revision used to identify a selected history view."""
        return self._master_revision

    @property
    def master_history(self) -> list[Msg]:
        """Return a copy so callers cannot mutate shared history outside promotion."""
        return deepcopy(self._master_history)

    @property
    def promotions(self) -> list[MasterHistoryPromotion]:
        """Return recorded promotion provenance without exposing session-owned DTOs."""
        return deepcopy(self._promotions)

    def start_state(
        self,
        state_id: str,
        master_projection: list[Msg],
        *,
        parent_state_run_id: str | None = None,
        parent_provider_call_id: str | None = None,
    ) -> StateHistory:
        """Create an isolated transcript from the caller-selected master projection.

        Parent linkage is checked against this session. Transcript messages are
        deep-copied because `Msg`, its metadata, and content parts are mutable.
        """
        if parent_state_run_id is not None and parent_state_run_id not in self._state_histories:
            raise ValueError(
                f"Parent state run '{parent_state_run_id}' is not active in this history session."
            )
        if parent_provider_call_id is not None and parent_state_run_id is None:
            raise ValueError("A parent provider call ID requires a parent state run ID.")

        state_history = StateHistory(
            state_id=state_id,
            state_run_id=str(uuid4()),
            parent_state_run_id=parent_state_run_id,
            parent_provider_call_id=parent_provider_call_id,
            master_history_revision=self._master_revision,
            messages=deepcopy(master_projection),
        )
        self._state_histories[state_history.state_run_id] = state_history
        return state_history

    def get_state(self, state_run_id: str) -> StateHistory:
        """Return the owned transcript for one active state run."""
        try:
            return self._state_histories[state_run_id]
        except KeyError as error:
            raise ValueError(f"State run '{state_run_id}' is not active.") from error

    def promote_to_master(self, origin_state_run_id: str, messages: list[Msg]) -> int:
        """Append caller-selected messages and advance shared history once.

        The originating state must still be active. An empty selection is a
        no-op and does not create a new revision.
        """
        self.get_state(origin_state_run_id)
        if not messages:
            return self._master_revision

        self._master_history.extend(deepcopy(messages))
        self._master_revision += 1
        self._promotions.append(
            MasterHistoryPromotion(
                origin_state_run_id=origin_state_run_id,
                revision=self._master_revision,
                message_count=len(messages),
            )
        )
        return self._master_revision

    def complete_state(self, state_run_id: str) -> None:
        """Release a completed transcript while leaving its caller untouched."""
        try:
            del self._state_histories[state_run_id]
        except KeyError as error:
            raise ValueError(f"State run '{state_run_id}' is not active.") from error
