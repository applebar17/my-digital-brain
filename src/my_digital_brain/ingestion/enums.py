from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    TRANSCRIPT = "transcript"
    IMAGE = "image"
    DOCUMENT = "document"
    LINK = "link"
    EXTERNAL = "external"


class SourceChannel(StrEnum):
    TELEGRAM = "telegram"
    MANUAL = "manual"
    API = "api"
    SYSTEM = "system"
    IMPORT = "import"


class MentionKind(StrEnum):
    PERSON = "person"
    PLACE = "place"
    EVENT = "event"
    ORGANIZATION = "organization"
    OBJECT = "object"
    ANIMAL = "animal"
    SOCIAL_CIRCLE = "social_circle"
    TOPIC = "topic"
    DATE = "date"
    RELATIONSHIP_CONTEXT = "relationship_context"
    PERCEPTION = "perception"
    CLAIM = "claim"
    METADATA = "metadata"


class ExtractionExecutionMode(StrEnum):
    SIMPLE_SINGLE_PASS = "simple_single_pass"
    FOCUSED_EXTRACTION = "focused_extraction"
    NEEDS_CONTEXT_EXPANSION = "needs_context_expansion"
    NEEDS_CLARIFICATION_FIRST = "needs_clarification_first"


class ExtractionTaskType(StrEnum):
    PERSON = "person"
    PLACE = "place"
    EVENT = "event"
    ORGANIZATION = "organization"
    OBJECT = "object"
    ANIMAL = "animal"
    SOCIAL_CIRCLE = "social_circle"
    TOPIC = "topic"
    CLAIM = "claim"
    RELATIONSHIP = "relationship"
    RELATIONSHIP_CONTEXT = "relationship_context"
    RELATIONSHIP_STATE = "relationship_state"
    PERCEPTION = "perception"
    METADATA_PATCH = "metadata_patch"
    LINK = "link"


class CandidateRefKind(StrEnum):
    CANDIDATE = "candidate"
    GRAPH_ALIAS = "graph_alias"
    GRAPH_ID = "graph_id"
    SOURCE = "source"
    EXTRACTION_RUN = "extraction_run"


class ClarificationStatus(StrEnum):
    PROPOSED = "proposed"
    WAITING_FOR_USER = "waiting_for_user"
    ANSWERED = "answered"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class ResolutionDecisionType(StrEnum):
    CREATE = "create"
    MATCH_EXISTING = "match_existing"
    MERGE = "merge"
    REJECT = "reject"
    KEEP_PENDING = "keep_pending"
    ASK_CLARIFICATION = "ask_clarification"


class GraphWritePlanStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    EXECUTED = "executed"
    FAILED = "failed"


class IngestionStatus(StrEnum):
    RECEIVED = "received"
    PLANNED = "planned"
    CANDIDATE_READY = "candidate_ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    VALIDATION_FAILED = "validation_failed"
    WRITE_PLAN_READY = "write_plan_ready"
    WRITTEN = "written"
    FAILED = "failed"
