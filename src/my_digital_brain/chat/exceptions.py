from __future__ import annotations


class ChatError(Exception):
    """Base class for chat runtime errors."""


class ChatNotFoundError(ChatError):
    """Raised when a chat session or process cannot be found."""


class ChatValidationError(ChatError):
    """Raised when a chat request cannot be handled safely."""
