"""Durable conversation contracts, projections, and application service."""

from product.application.conversations.contracts import (
    AppendConversationMessageCommandDTO,
    AppendModelContextCommandDTO,
    ConversationDTO,
    ConversationEntryDTO,
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
from product.application.conversations.service import (
    ConversationApplicationService,
    PreparedConversationTurn,
)

__all__ = [
    "AppendConversationMessageCommandDTO",
    "AppendModelContextCommandDTO",
    "ConversationApplicationService",
    "ConversationDTO",
    "ConversationEntryDTO",
    "ConversationHistoryProjector",
    "ConversationMessageEntryDTO",
    "ConversationMessageRole",
    "ConversationRepository",
    "CreateConversationCommandDTO",
    "FrontendConversationHistoryDTO",
    "ModelContextEntryDTO",
    "ModelHistoryProjectionDTO",
    "PreparedConversationTurn",
    "QuestionAnswerEntryDTO",
    "SubmitConversationMessageDTO",
    "UpsertQuestionAnswerCommandDTO",
]
