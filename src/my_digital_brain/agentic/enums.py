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
    REASONING_CHECKPOINT = "reasoning_checkpoint"
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


class ContradictionDecision(StrEnum):
    NO_CONFLICT = "no_conflict"
    NUANCE = "nuance"
    TEMPORAL_UPDATE = "temporal_update"
    CONTRADICTION = "contradiction"
    NEEDS_CLARIFICATION = "needs_clarification"


class ContradictionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContradictionGraphAction(StrEnum):
    ALLOW_WRITE = "allow_write"
    WRITE_AS_DISPUTED = "write_as_disputed"
    CREATE_CONTRADICTION_RECORD = "create_contradiction_record"
    CREATE_RELATIONSHIP_STATE = "create_relationship_state"
    ASK_USER = "ask_user"


class ContradictionResultIntent(StrEnum):
    NEEDS_CONTEXT = "needs_context"
    NEEDS_CLARIFICATION = "needs_clarification"
    EMIT_VERDICT = "emit_verdict"
    FAIL_SAFE = "fail_safe"


class ReasoningInsightKind(StrEnum):
    CLARIFICATION_NEED = "clarification_need"
    ENTITY_UNDERSTANDING = "entity_understanding"
    NODE_VS_METADATA = "node_vs_metadata"
    RELATIONSHIP_INTENT = "relationship_intent"
    PROFILE_MEMORY = "profile_memory"
    PERCEPTION = "perception"
    CONTRADICTION_RISK = "contradiction_risk"
    PRIVACY_TRUST = "privacy_trust"
    PROVENANCE_REQUIREMENT = "provenance_requirement"
    CONTEXT_GAP = "context_gap"
    EXTRACTION_STRATEGY = "extraction_strategy"
    WRITE_GUARDRAIL = "write_guardrail"


class ReasoningStorageRecommendationType(StrEnum):
    CREATE_NODE = "create_node"
    UPDATE_NODE = "update_node"
    CREATE_RELATIONSHIP = "create_relationship"
    CREATE_RELATIONSHIP_CONTEXT = "create_relationship_context"
    CREATE_CLAIM = "create_claim"
    CREATE_PERCEPTION = "create_perception"
    CREATE_PROFILE_MEMORY = "create_profile_memory"
    STORE_AS_METADATA = "store_as_metadata"
    ASK_CLARIFICATION = "ask_clarification"
    REQUEST_MORE_CONTEXT = "request_more_context"
    SKIP = "skip"


class CorrectionAction(StrEnum):
    NO_CHANGE = "no_change"
    PATCH_NODE = "patch_node"
    PATCH_RELATIONSHIP = "patch_relationship"
    UPDATE_RELATIONSHIP_CONTEXT = "update_relationship_context"
    UPDATE_CONTACT_POINT = "update_contact_point"
    MARK_DISPUTED = "mark_disputed"
    ARCHIVE_MEMORY = "archive_memory"
    NEEDS_TARGET = "needs_target"


class ConfirmationRiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProfileMemoryCategory(StrEnum):
    COMMUNICATION = "communication"
    PERSONALITY = "personality"
    GOALS = "goals"
    PREFERENCES = "preferences"
    PRIVACY = "privacy"
    WORK_STYLE = "work_style"
    INTERESTS = "interests"
    EMOTIONAL_PATTERN = "emotional_pattern"


class ProfileMemoryStability(StrEnum):
    TEMPORARY = "temporary"
    RECURRING = "recurring"
    STABLE = "stable"
    USER_CONFIRMED = "user_confirmed"


class ProfileMemoryVisibility(StrEnum):
    HIDDEN = "hidden"
    RETRIEVABLE = "retrievable"
    PROMPT_ALLOWED = "prompt_allowed"


class MaintenanceSuggestionType(StrEnum):
    REVIEW_CONTRADICTION = "review_contradiction"
    MARK_STALE = "mark_stale"
    MARK_EXPIRED = "mark_expired"
    MARK_CONFIRMED = "mark_confirmed"
    ARCHIVE_MEMORY = "archive_memory"
    UPDATE_CONTACT_POINT = "update_contact_point"
    ATTACH_EVIDENCE = "attach_evidence"
    PROMOTE_METADATA = "promote_metadata"
    PROPOSE_MERGE = "propose_merge"
