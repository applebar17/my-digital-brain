"""In-process persistence boundary for nested user interactions."""

from threading import Lock

from product.agentic.contracts import PausedStateContinuationDTO
from product.application.interactions.models import (
    PendingNestedInteractionDTO,
    PendingUserQuestionDTO,
)


class InteractionContinuationStore:
    """Retain child and parent continuations until one interaction resolves.

    This in-process implementation establishes the product contract used during
    Wave 4. Wave 5 replaces its storage mechanism at the API composition boundary
    without changing clarification or agentic-state behavior.
    """

    def __init__(self) -> None:
        self._records: dict[str, PendingNestedInteractionDTO] = {}
        self._lock = Lock()

    def register_child(
        self,
        continuation: PausedStateContinuationDTO[PendingUserQuestionDTO],
    ) -> PendingUserQuestionDTO:
        """Store one newly paused child and return its user-facing packet."""
        pending_packets = [
            call.interaction_request.interaction_packet
            for call in continuation.tool_batch.calls
            if call.interaction_request is not None
        ]
        if len(pending_packets) != 1:
            raise ValueError(
                "A clarification child must expose exactly one pending user question per run."
            )
        packet = PendingUserQuestionDTO.model_validate(pending_packets[0])
        with self._lock:
            if packet.interaction_ref in self._records:
                raise ValueError(
                    f"Interaction '{packet.interaction_ref}' is already registered."
                )
            self._records[packet.interaction_ref] = PendingNestedInteractionDTO(
                interaction=packet,
                child_continuation=continuation.model_copy(deep=True),
            )
        return packet

    def attach_parent(
        self,
        interaction_ref: str,
        continuation: PausedStateContinuationDTO[PendingUserQuestionDTO],
        provider_call_id: str,
    ) -> PendingNestedInteractionDTO:
        """Attach the original parent pause and provider call to a child record."""
        with self._lock:
            record = self._required_record(interaction_ref)
            if record.parent_continuation is not None:
                if record.parent_provider_call_id != provider_call_id:
                    raise ValueError(
                        f"Interaction '{interaction_ref}' is already attached to another "
                        "parent tool call."
                    )
                return record.model_copy(deep=True)
            child_continuation = record.child_continuation.model_copy(deep=True)
            child_continuation.state_history.parent_state_run_id = (
                continuation.state_history.state_run_id
            )
            child_continuation.state_history.parent_provider_call_id = provider_call_id
            updated = record.model_copy(
                update={
                    "child_continuation": child_continuation,
                    "parent_continuation": continuation.model_copy(deep=True),
                    "parent_provider_call_id": provider_call_id,
                },
                deep=True,
            )
            self._records[interaction_ref] = updated
            return updated.model_copy(deep=True)

    def claim(self, interaction_ref: str) -> PendingNestedInteractionDTO:
        """Atomically claim one interaction so answer and timeout cannot both resolve it."""
        with self._lock:
            record = self._required_record(interaction_ref)
            if record.claimed:
                raise ValueError(f"Interaction '{interaction_ref}' has already been resolved.")
            if record.parent_continuation is None or record.parent_provider_call_id is None:
                raise ValueError(
                    f"Interaction '{interaction_ref}' is not attached to its parent continuation."
                )
            claimed = record.model_copy(update={"claimed": True}, deep=True)
            self._records[interaction_ref] = claimed
            return claimed.model_copy(deep=True)

    def get(self, interaction_ref: str) -> PendingNestedInteractionDTO:
        """Return a defensive copy for answer validation before atomic resolution."""
        with self._lock:
            return self._required_record(interaction_ref).model_copy(deep=True)

    def contains(self, interaction_ref: str) -> bool:
        """Return whether this store owns the interaction reference."""
        with self._lock:
            return interaction_ref in self._records

    def _required_record(self, interaction_ref: str) -> PendingNestedInteractionDTO:
        try:
            return self._records[interaction_ref]
        except KeyError as error:
            raise ValueError(
                f"Interaction '{interaction_ref}' is unknown or no longer available."
            ) from error

