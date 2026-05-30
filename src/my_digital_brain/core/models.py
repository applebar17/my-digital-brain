from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from my_digital_brain.core.enums import LifecycleState, PrivacyLevel, TrustLevel


class TemporalFields(BaseModel):
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    source_time: datetime | None = None
    time_precision: str | None = None
    original_time_text: str | None = None


class GraphRecordBase(BaseModel):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    description: str | None = None
    emotional_summary: str | None = None
    emotional_valence: str | None = None
    emotional_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    emotion_tags: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    trust_level: TrustLevel | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRelationshipBase(BaseModel):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    emotional_summary: str | None = None
    emotional_valence: str | None = None
    emotional_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    emotion_tags: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    trust_level: TrustLevel | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    source_ids: list[str] = Field(default_factory=list)
    extraction_run_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceReference(BaseModel):
    source_ids: list[str] = Field(default_factory=list)
    extraction_run_ids: list[str] = Field(default_factory=list)


class GraphEntityReference(BaseModel):
    id: str
    label: str
