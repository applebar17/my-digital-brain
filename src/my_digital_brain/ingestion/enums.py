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


class ExtractionExecutionMode(StrEnum):
    FOCUSED_EXTRACTION = "focused_extraction"


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
    PROFILE_MEMORY = "profile_memory"
    MEMORY_LOG = "memory_log"
    LINK = "link"


class CandidateRefKind(StrEnum):
    CANDIDATE = "candidate"
    GRAPH_ALIAS = "graph_alias"
    GRAPH_ID = "graph_id"
    SOURCE = "source"
    EXTRACTION_RUN = "extraction_run"


class ResolutionDecisionType(StrEnum):
    CREATE = "create"
    MATCH_EXISTING = "match_existing"
    MERGE = "merge"
    REJECT = "reject"
    KEEP_PENDING = "keep_pending"


class GraphWritePlanStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    EXECUTED = "executed"
    FAILED = "failed"


class IngestionStatus(StrEnum):
    RECEIVED = "received"
    PLANNED = "planned"
    CANDIDATE_READY = "candidate_ready"
    VALIDATION_FAILED = "validation_failed"
    WRITE_PLAN_READY = "write_plan_ready"
    WRITTEN = "written"
    FAILED = "failed"
