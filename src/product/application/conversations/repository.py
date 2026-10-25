"""Persistence protocol for owner-scoped durable conversations."""

from typing import Protocol

from product.application.conversations.contracts import (
    AppendConversationMessageCommandDTO,
    AppendModelContextCommandDTO,
    ConversationDTO,
    ConversationEntryDTO,
    ConversationMessageEntryDTO,
    CreateConversationCommandDTO,
    ModelContextEntryDTO,
    QuestionAnswerEntryDTO,
    UpsertQuestionAnswerCommandDTO,
)


class ConversationRepository(Protocol):
    """Store typed conversation entries while enforcing application-user ownership.

    Concrete adapters own transactions and persisted identifiers. Message
    appends are idempotent for a non-null client message identifier, while a
    question/answer upsert preserves one entry per interaction reference.
    """

    def create_conversation(
        self,
        owner_id: str,
        command: CreateConversationCommandDTO,
    ) -> ConversationDTO:
        """Create and return one conversation scoped to the supplied owner."""
        ...

    def get_conversation(self, owner_id: str, conversation_id: str) -> ConversationDTO:
        """Return the conversation only when it belongs to the supplied owner."""
        ...

    def append_message(
        self,
        owner_id: str,
        command: AppendConversationMessageCommandDTO,
    ) -> ConversationMessageEntryDTO:
        """Append one message or return its existing idempotent user entry."""
        ...

    def upsert_question_answer(
        self,
        owner_id: str,
        command: UpsertQuestionAnswerCommandDTO,
    ) -> QuestionAnswerEntryDTO:
        """Create a pending question or update that interaction with its answer."""
        ...

    def append_model_context(
        self,
        owner_id: str,
        command: AppendModelContextCommandDTO,
    ) -> ModelContextEntryDTO:
        """Append compact context deliberately retained for later root model turns."""
        ...

    def list_entries(
        self,
        owner_id: str,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None = None,
    ) -> list[ConversationEntryDTO]:
        """Return the newest bounded entries in ascending conversation order."""
        ...
