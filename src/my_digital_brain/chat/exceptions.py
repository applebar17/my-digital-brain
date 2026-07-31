from __future__ import annotations


class ChatError(Exception):
    """Base class for chat runtime errors."""


class ChatNotFoundError(ChatError):
    """Raised when a chat session or process cannot be found."""


class ChatValidationError(ChatError):
    """Raised when a chat request cannot be handled safely."""


class ClarificationValidationError(ChatValidationError):
    """Structured validation failure for a clarification answer submission."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "clarification_answer_invalid",
        packet_id: str | None = None,
        frame_id: str | None = None,
        question_ids: list[str] | None = None,
        retryable: bool = True,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.packet_id = packet_id
        self.frame_id = frame_id
        self.question_ids = list(question_ids or [])
        self.retryable = retryable
        self.details = dict(details or {})
