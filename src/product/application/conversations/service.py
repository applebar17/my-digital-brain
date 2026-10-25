"""Application service joining durable conversations to runtime history initialization."""

from dataclasses import dataclass

from product.agentic.history import AgenticHistorySession
from product.application.conversations.contracts import (
    AppendConversationMessageCommandDTO,
    AppendModelContextCommandDTO,
    ConversationDTO,
    ConversationMessageEntryDTO,
    ConversationMessageRole,
    CreateConversationCommandDTO,
    FrontendConversationHistoryDTO,
    ModelContextEntryDTO,
    ModelHistoryProjectionDTO,
    QuestionAnswerEntryDTO,
    SubmitConversationMessageDTO,
    UpsertQuestionAnswerCommandDTO,
)
from product.application.conversations.history import ConversationHistoryProjector
from product.application.conversations.repository import ConversationRepository


@dataclass(frozen=True, slots=True)
class PreparedConversationTurn:
    """Persisted current message and runtime history prepared for the root state."""

    conversation: ConversationDTO
    user_entry: ConversationMessageEntryDTO
    model_history: ModelHistoryProjectionDTO
    history_session: AgenticHistorySession


class ConversationApplicationService:
    """Coordinate conversation persistence and deterministic history projections."""

    def __init__(
        self,
        repository: ConversationRepository,
        projector: ConversationHistoryProjector,
        *,
        model_history_entry_limit: int = 50,
        model_history_message_limit: int = 30,
    ) -> None:
        self.repository = repository
        self.projector = projector
        self.model_history_entry_limit = model_history_entry_limit
        self.model_history_message_limit = model_history_message_limit

    def create_conversation(
        self,
        owner_id: str,
        command: CreateConversationCommandDTO,
    ) -> ConversationDTO:
        """Create an owner-scoped conversation through `ConversationRepository`.

        Side effects:
            Persists one conversation through the configured repository.
        """
        return self.repository.create_conversation(owner_id, command)

    def prepare_turn(
        self,
        owner_id: str,
        submission: SubmitConversationMessageDTO,
    ) -> PreparedConversationTurn:
        """Persist the current user message and initialize its prior runtime history.

        Dependencies:
            - `ConversationRepository` verifies ownership, performs the
              idempotent append, and loads recent durable entries.
            - `ConversationHistoryProjector` excludes the current entry and
              produces canonical prior model messages.
            - `AgenticHistorySession` owns the resulting runtime history.

        Side effects:
            Persists the user message. It does not invoke an LLM or append an
            assistant response; `ConversationEntryState` owns that next step.
        """
        conversation = self.repository.get_conversation(owner_id, submission.conversation_id)
        user_entry = self.repository.append_message(
            owner_id,
            AppendConversationMessageCommandDTO(
                conversation_id=submission.conversation_id,
                role=ConversationMessageRole.USER,
                text=submission.text,
                client_message_id=submission.client_message_id,
            ),
        )
        entries = self.repository.list_entries(
            owner_id,
            submission.conversation_id,
            limit=self.model_history_entry_limit,
        )
        model_history = self.projector.model_history(
            entries,
            max_messages=self.model_history_message_limit,
            excluded_entry_ids={user_entry.entry_id},
        )
        return PreparedConversationTurn(
            conversation=conversation,
            user_entry=user_entry,
            model_history=model_history,
            history_session=AgenticHistorySession(model_history.messages),
        )

    def complete_turn(
        self,
        owner_id: str,
        conversation_id: str,
        assistant_text: str,
    ) -> ConversationMessageEntryDTO:
        """Persist the completed root-state response as one visible assistant message.

        Dependencies:
            `ConversationRepository` verifies ownership and appends the durable
            message. Provider transcripts and tool outputs are not persisted here.
        """
        return self.repository.append_message(
            owner_id,
            AppendConversationMessageCommandDTO(
                conversation_id=conversation_id,
                role=ConversationMessageRole.ASSISTANT,
                text=assistant_text,
            ),
        )

    def upsert_question_answer(
        self,
        owner_id: str,
        command: UpsertQuestionAnswerCommandDTO,
    ) -> QuestionAnswerEntryDTO:
        """Persist a presented question and later attach its answer exactly once."""
        return self.repository.upsert_question_answer(owner_id, command)

    def append_model_context(
        self,
        owner_id: str,
        command: AppendModelContextCommandDTO,
    ) -> ModelContextEntryDTO:
        """Persist explicitly promoted compact context for later root model turns."""
        return self.repository.append_model_context(owner_id, command)

    def frontend_history(
        self,
        owner_id: str,
        conversation_id: str,
        *,
        limit: int = 50,
        before_sequence: int | None = None,
    ) -> FrontendConversationHistoryDTO:
        """Load one frontend page while excluding model-only durable context.

        Dependencies:
            `ConversationRepository` supplies an owner-scoped page and
            `ConversationHistoryProjector` renders its visible variants.
        """
        requested_limit = max(1, limit)
        entries = self.repository.list_entries(
            owner_id,
            conversation_id,
            limit=requested_limit + 1,
            before_sequence=before_sequence,
        )
        has_older = len(entries) > requested_limit
        page_entries = entries[-requested_limit:]
        next_before_sequence = page_entries[0].sequence if has_older and page_entries else None
        return self.projector.frontend_history(
            page_entries,
            next_before_sequence=next_before_sequence,
        )
