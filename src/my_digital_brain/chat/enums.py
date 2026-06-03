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
    NEEDS_USER_INPUT = "needs_user_input"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PendingProcessKind(StrEnum):
    MEMORY_INGESTION = "memory_ingestion"
    MEMORY_QUERY = "memory_query"
    MEMORY_CORRECTION = "memory_correction"


class PendingProcessStatus(StrEnum):
    PENDING = "pending"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ChatDiagnosticLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
