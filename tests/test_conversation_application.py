from __future__ import annotations

from datetime import UTC, datetime

from product.application.conversations import (
    AppendConversationMessageCommandDTO,
    AppendModelContextCommandDTO,
    ConversationApplicationService,
    ConversationDTO,
    ConversationEntryDTO,
    ConversationHistoryProjector,
    ConversationMessageEntryDTO,
    ConversationMessageRole,
    CreateConversationCommandDTO,
    ModelContextEntryDTO,
    QuestionAnswerEntryDTO,
    SubmitConversationMessageDTO,
    UpsertQuestionAnswerCommandDTO,
)


class InMemoryConversationRepository:
    """Functional test adapter implementing the owner-scoped repository contract."""

    def __init__(self) -> None:
        self.conversations: dict[str, ConversationDTO] = {}
        self.entries: dict[str, list[ConversationEntryDTO]] = {}
        self.next_conversation = 1
        self.next_entry = 1

    def create_conversation(
        self,
        owner_id: str,
        command: CreateConversationCommandDTO,
    ) -> ConversationDTO:
        now = datetime.now(UTC)
        conversation = ConversationDTO(
            conversation_id=f"conversation-{self.next_conversation}",
            owner_id=owner_id,
            title=command.title or "New chat",
            created_at=now,
            updated_at=now,
        )
        self.next_conversation += 1
        self.conversations[conversation.conversation_id] = conversation
        self.entries[conversation.conversation_id] = []
        return conversation

    def get_conversation(self, owner_id: str, conversation_id: str) -> ConversationDTO:
        conversation = self.conversations[conversation_id]
        if conversation.owner_id != owner_id:
            raise ValueError("Conversation does not belong to the supplied owner.")
        return conversation

    def append_message(
        self,
        owner_id: str,
        command: AppendConversationMessageCommandDTO,
    ) -> ConversationMessageEntryDTO:
        self.get_conversation(owner_id, command.conversation_id)
        if command.client_message_id is not None:
            for entry in self.entries[command.conversation_id]:
                if (
                    isinstance(entry, ConversationMessageEntryDTO)
                    and entry.client_message_id == command.client_message_id
                ):
                    return entry
        entry = ConversationMessageEntryDTO(
            entry_id=self._entry_id(),
            conversation_id=command.conversation_id,
            sequence=len(self.entries[command.conversation_id]) + 1,
            created_at=datetime.now(UTC),
            role=command.role,
            text=command.text,
            client_message_id=command.client_message_id,
        )
        self.entries[command.conversation_id].append(entry)
        return entry

    def upsert_question_answer(
        self,
        owner_id: str,
        command: UpsertQuestionAnswerCommandDTO,
    ) -> QuestionAnswerEntryDTO:
        self.get_conversation(owner_id, command.conversation_id)
        entries = self.entries[command.conversation_id]
        for index, entry in enumerate(entries):
            if (
                isinstance(entry, QuestionAnswerEntryDTO)
                and entry.interaction_ref == command.interaction_ref
            ):
                updated = entry.model_copy(
                    update={
                        "question": command.question,
                        "answer": command.answer if command.answer is not None else entry.answer,
                    }
                )
                entries[index] = updated
                return updated
        entry = QuestionAnswerEntryDTO(
            entry_id=self._entry_id(),
            conversation_id=command.conversation_id,
            sequence=len(entries) + 1,
            created_at=datetime.now(UTC),
            interaction_ref=command.interaction_ref,
            question=command.question,
            answer=command.answer,
        )
        entries.append(entry)
        return entry

    def append_model_context(
        self,
        owner_id: str,
        command: AppendModelContextCommandDTO,
    ) -> ModelContextEntryDTO:
        self.get_conversation(owner_id, command.conversation_id)
        entry = ModelContextEntryDTO(
            entry_id=self._entry_id(),
            conversation_id=command.conversation_id,
            sequence=len(self.entries[command.conversation_id]) + 1,
            created_at=datetime.now(UTC),
            role=command.role,
            content=command.content,
        )
        self.entries[command.conversation_id].append(entry)
        return entry

    def list_entries(
        self,
        owner_id: str,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None = None,
    ) -> list[ConversationEntryDTO]:
        self.get_conversation(owner_id, conversation_id)
        entries = self.entries[conversation_id]
        if before_sequence is not None:
            entries = [entry for entry in entries if entry.sequence < before_sequence]
        return list(entries[-limit:])

    def _entry_id(self) -> str:
        entry_id = f"entry-{self.next_entry}"
        self.next_entry += 1
        return entry_id


def test_turn_preparation_builds_distinct_frontend_and_model_history() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationApplicationService(repository, ConversationHistoryProjector())
    conversation = service.create_conversation("owner-1", CreateConversationCommandDTO())

    repository.append_message(
        "owner-1",
        AppendConversationMessageCommandDTO(
            conversation_id=conversation.conversation_id,
            role=ConversationMessageRole.USER,
            text="Remember Amos.",
            client_message_id="client-1",
        ),
    )
    service.upsert_question_answer(
        "owner-1",
        UpsertQuestionAnswerCommandDTO(
            conversation_id=conversation.conversation_id,
            interaction_ref="which-amos",
            question="Which Amos do you mean?",
            answer="Amos Vignaroli",
        ),
    )
    service.append_model_context(
        "owner-1",
        AppendModelContextCommandDTO(
            conversation_id=conversation.conversation_id,
            role=ConversationMessageRole.ASSISTANT,
            content="The previous ingestion completed successfully.",
        ),
    )

    prepared = service.prepare_turn(
        "owner-1",
        SubmitConversationMessageDTO(
            conversation_id=conversation.conversation_id,
            client_message_id="client-2",
            text="What did I tell you?",
        ),
    )
    frontend = service.frontend_history("owner-1", conversation.conversation_id)

    assert [message.role for message in prepared.model_history.messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert [message.as_text() for message in prepared.model_history.messages] == [
        "Remember Amos.",
        "Which Amos do you mean?",
        "Amos Vignaroli",
        "The previous ingestion completed successfully.",
    ]
    assert prepared.history_session.master_history == prepared.model_history.messages
    assert [item.kind for item in frontend.items] == [
        "message",
        "question_answer",
        "message",
    ]
    assert all(not isinstance(item, ModelContextEntryDTO) for item in frontend.items)


def test_retried_submission_reuses_user_entry_without_duplicating_current_history() -> None:
    repository = InMemoryConversationRepository()
    service = ConversationApplicationService(repository, ConversationHistoryProjector())
    conversation = service.create_conversation("owner-1", CreateConversationCommandDTO())
    submission = SubmitConversationMessageDTO(
        conversation_id=conversation.conversation_id,
        client_message_id="same-client-message",
        text="Store this once.",
    )

    first = service.prepare_turn("owner-1", submission)
    second = service.prepare_turn("owner-1", submission)

    assert first.user_entry.entry_id == second.user_entry.entry_id
    assert repository.list_entries("owner-1", conversation.conversation_id, limit=10) == [
        first.user_entry
    ]
    assert first.model_history.messages == []
    assert second.model_history.messages == []


def test_question_answer_is_updated_once_and_selected_as_an_atomic_model_unit() -> None:
    repository = InMemoryConversationRepository()
    projector = ConversationHistoryProjector()
    service = ConversationApplicationService(repository, projector)
    conversation = service.create_conversation("owner-1", CreateConversationCommandDTO())
    pending = UpsertQuestionAnswerCommandDTO(
        conversation_id=conversation.conversation_id,
        interaction_ref="surname-gap",
        question="What is Gabriele's surname?",
    )

    first = service.upsert_question_answer("owner-1", pending)
    completed = service.upsert_question_answer(
        "owner-1",
        pending.model_copy(update={"answer": "Lucci"}),
    )
    entries = repository.list_entries("owner-1", conversation.conversation_id, limit=10)

    assert first.entry_id == completed.entry_id
    assert completed.answer == "Lucci"
    assert len(entries) == 1
    assert projector.model_history(entries, max_messages=1).messages == []
    projected = projector.model_history(entries, max_messages=2)
    assert [message.as_text() for message in projected.messages] == [
        "What is Gabriele's surname?",
        "Lucci",
    ]
