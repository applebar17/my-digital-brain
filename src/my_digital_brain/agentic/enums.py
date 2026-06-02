from __future__ import annotations

from enum import StrEnum


class AgenticNodeKind(StrEnum):
    AGENTIC_STATE = "AS"
    LLM_PROCEDURE = "LP"
    BACKEND_PROCESS = "BP"
    RUNTIME_STATE = "RS"


class AgenticStateId(StrEnum):
    CONVERSATION_ENTRY = "conversation_entry"
    PENDING_PROCESS_REVIEW = "pending_process_review"
    MEMORY_INGESTION_PLANNING = "memory_ingestion_planning"
    CONTRADICTION_REVIEW = "contradiction_review"
    MEMORY_QUERY = "memory_query"
    CORRECTION_INTAKE = "correction_intake"


class NeutralMessageKind(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    ASSISTANT_TOOL_CALL = "assistant_tool_call"
    TOOL_OUTPUT = "tool_output"
    COMPACTED_SUMMARY = "compacted_summary"


class PendingMessageIntent(StrEnum):
    CLARIFICATION_ANSWER = "clarification_answer"
    NEW_MEMORY = "new_memory"
    QUESTION = "question"
    CORRECTION = "correction"
    CANCEL = "cancel"
    SKIP = "skip"
    PAUSE = "pause"
    UNCLEAR = "unclear"
    NORMAL_CHAT = "normal_chat"


class ToolResultStatus(StrEnum):
    OK = "ok"
    ACCEPTED = "accepted"
    NEEDS_USER_INPUT = "needs_user_input"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ChannelModality(StrEnum):
    TEXT = "text"
    VOICE_TRANSCRIPT = "voice_transcript"
    AUDIO_TRANSCRIPT = "audio_transcript"
    IMAGE_DERIVED_TEXT = "image_derived_text"
    MEDIA_ONLY = "media_only"


class ResponseRenderStyle(StrEnum):
    PLAIN_TEXT = "plain_text"
    SHORT_CHAT = "short_chat"
    RICH_WEB = "rich_web"
