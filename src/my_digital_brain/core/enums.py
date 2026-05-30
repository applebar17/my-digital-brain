from __future__ import annotations

from enum import StrEnum


class TrustLevel(StrEnum):
    USER_CONFIRMED = "user_confirmed"
    SOURCE_STATED = "source_stated"
    LLM_INFERRED = "llm_inferred"
    SYSTEM_DERIVED = "system_derived"
    EXTERNALLY_ENRICHED = "externally_enriched"
    CONTRADICTED = "contradicted"
    STALE = "stale"


class PrivacyLevel(StrEnum):
    NORMAL = "normal"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    LOCAL_ONLY = "local_only"
    HIDDEN = "hidden"


class LifecycleState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    DISPUTED = "disputed"
    STALE = "stale"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    DELETED = "deleted"
