"""Deterministic frontend and model projections of durable conversation entries."""

from collections.abc import Iterable, Set

from product.ai.ai_clients.protocols.protocol_chat import Msg
from product.application.conversations.contracts import (
    ConversationEntryDTO,
    ConversationMessageEntryDTO,
    FrontendConversationHistoryDTO,
    ModelContextEntryDTO,
    ModelHistoryProjectionDTO,
    QuestionAnswerEntryDTO,
)


class ConversationHistoryProjector:
    """Build consumer-specific history views without duplicating stored entries."""

    def frontend_history(
        self,
        entries: Iterable[ConversationEntryDTO],
        *,
        next_before_sequence: int | None = None,
    ) -> FrontendConversationHistoryDTO:
        """Return ordered visible messages and interactions, excluding model-only context."""
        ordered = self._ordered(entries)
        return FrontendConversationHistoryDTO(
            items=[
                entry
                for entry in ordered
                if isinstance(entry, ConversationMessageEntryDTO | QuestionAnswerEntryDTO)
            ],
            next_before_sequence=next_before_sequence,
        )

    def model_history(
        self,
        entries: Iterable[ConversationEntryDTO],
        *,
        max_messages: int,
        excluded_entry_ids: Set[str] = frozenset(),
    ) -> ModelHistoryProjectionDTO:
        """Select a recent bounded model view while keeping question/answer pairs atomic.

        Ordinary messages and explicit compact model context become one message.
        A completed question/answer interaction becomes two adjacent messages;
        a pending interaction remains owned by its paused continuation.
        """
        if max_messages < 1:
            return ModelHistoryProjectionDTO()

        groups = [
            group
            for entry in self._ordered(entries)
            if entry.entry_id not in excluded_entry_ids
            if (group := self._model_group(entry))
        ]
        selected_reversed: list[list[Msg]] = []
        selected_count = 0
        for group in reversed(groups):
            if selected_count + len(group) > max_messages:
                break
            selected_reversed.append(group)
            selected_count += len(group)

        messages = [message for group in reversed(selected_reversed) for message in group]
        return ModelHistoryProjectionDTO(messages=messages)

    @staticmethod
    def _ordered(entries: Iterable[ConversationEntryDTO]) -> list[ConversationEntryDTO]:
        return sorted(entries, key=lambda entry: entry.sequence)

    @staticmethod
    def _model_group(entry: ConversationEntryDTO) -> list[Msg]:
        if isinstance(entry, ConversationMessageEntryDTO):
            return [Msg(role=entry.role.value, content=entry.text)]
        if isinstance(entry, QuestionAnswerEntryDTO):
            if entry.answer is None:
                return []
            return [
                Msg(role="assistant", content=entry.question),
                Msg(role="user", content=entry.answer),
            ]
        if isinstance(entry, ModelContextEntryDTO):
            return [Msg(role=entry.role.value, content=entry.content)]
        raise TypeError(f"Unsupported conversation entry type: {type(entry).__name__}")
