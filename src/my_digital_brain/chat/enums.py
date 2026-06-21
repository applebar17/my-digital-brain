from __future__ import annotations

from enum import StrEnum


class ChatChannel(StrEnum):
    TELEGRAM = "telegram"
    WEB = "web"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConversationMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatResponseStatus(StrEnum):
    OK = "ok"
    ACCEPTED = "accepted"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ChatDiagnosticLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
