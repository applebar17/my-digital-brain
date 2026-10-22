"""Own one orchestration's shared history and isolated state transcripts."""

from copy import deepcopy
from typing import Literal, cast
from uuid import uuid4

from pydantic import BaseModel

from product.agentic.contracts import (
    MasterHistoryPromotion,
    PausedStateContinuationDTO,
    StateHistory,
    ToolCallBatchPauseDTO,
)
from product.ai.ai_clients.protocols.protocol_chat import Msg


class AgenticHistorySession:
    """Manage shared history revisions and active state-local transcripts."""

    def __init__(self, master_history: list[Msg] | None = None) -> None:
        """Copy caller-loaded conversation messages into this session's ownership."""
        self._master_history = deepcopy(master_history or [])
        self._master_revision = 0
        self._state_histories: dict[str, StateHistory] = {}
        self._promotions: list[MasterHistoryPromotion] = []
        self._paused_state_run_ids: set[str] = set()

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
        selected_history: list[Msg],
        *,
        parent_state_run_id: str | None = None,
        parent_provider_call_id: str | None = None,
    ) -> StateHistory:
        """Create an isolated transcript from the history projection selected by the caller.

        The caller—not this session or the child state—decides whether the
        projection comes from shared master history, a parent transcript, or a
        filtered combination. Parent linkage is checked against this session.
        Transcript messages are deep-copied because `Msg`, its metadata, and
        content parts are mutable.
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
            messages=deepcopy(selected_history),
        )
        self._state_histories[state_history.state_run_id] = state_history
        return state_history

    def get_state(self, state_run_id: str) -> StateHistory:
        """Return the owned transcript for one active state run."""
        try:
            return self._state_histories[state_run_id]
        except KeyError as error:
            raise ValueError(f"State run '{state_run_id}' is not active.") from error

    def pause_state[InteractionDTO: BaseModel](
        self,
        state_run_id: str,
        tool_batch: ToolCallBatchPauseDTO[InteractionDTO],
        *,
        execution_stage: Literal["reasoning", "planning", "main"] = "main",
        main_state_history: StateHistory | None = None,
    ) -> PausedStateContinuationDTO[InteractionDTO]:
        """Snapshot a state's transcript and all unresolved calls in one tool batch.

        The caller returns this continuation to the application/UI boundary. No
        provider call resumes until every interaction in the batch has a result.
        """
        state = self.get_state(state_run_id)
        if state_run_id in self._paused_state_run_ids:
            raise ValueError(f"State run '{state_run_id}' is already paused.")
        first_pending = next(
            call for call in tool_batch.calls if call.interaction_request is not None
        )
        interaction_type = type(first_pending.interaction_request.interaction_packet)
        continuation_type = PausedStateContinuationDTO[interaction_type]
        continuation = continuation_type(
            state_history=deepcopy(state),
            tool_batch=deepcopy(tool_batch),
            execution_stage=execution_stage,
            main_state_history=deepcopy(main_state_history),
        )
        self._paused_state_run_ids.add(state_run_id)
        return cast(PausedStateContinuationDTO[InteractionDTO], continuation)

    def resume_state[InteractionDTO: BaseModel](
        self, continuation: PausedStateContinuationDTO[InteractionDTO]
    ) -> StateHistory:
        """Restore the paused transcript snapshot and make the state active again.

        The state/client boundary restores the local transcript; the client
        retains the continuation until every pending call has an output.
        """
        state_run_id = continuation.state_history.state_run_id
        state = self.get_state(state_run_id)
        if state_run_id not in self._paused_state_run_ids:
            raise ValueError(f"State run '{state_run_id}' is not paused.")

        state.messages = deepcopy(continuation.state_history.messages)
        self._paused_state_run_ids.remove(state_run_id)
        return state

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
        self._paused_state_run_ids.discard(state_run_id)
