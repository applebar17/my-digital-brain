from __future__ import annotations

from my_digital_brain.core.enums import LifecycleState

NORMALIZED_NAME_LABELS = {
    "Person",
    "Place",
    "Organization",
    "Object",
    "Animal",
    "SocialCircle",
    "Topic",
}
IMMUTABLE_PATCH_FIELDS = {"id", "created_at", "is_owner"}
OWNER_ALIAS = "OWNER"
AFFECTIVE_FIELD_NAMES = {
    "emotional_summary",
    "emotional_valence",
    "emotional_intensity",
    "emotion_tags",
    "original_user_words",
}
RELATIONSHIP_CONTEXT_CURRENT_FIELDS = {
    "description",
    "status",
    "closeness",
    "emotional_summary",
    "emotional_valence",
    "emotional_intensity",
    "emotion_tags",
    "original_user_words",
    "valid_from",
    "valid_to",
    "resolved_start",
    "resolved_end",
    "time_precision",
    "time_basis",
    "timezone",
    "original_time_text",
}
NODE_LIKE_TARGET_KINDS = {
    "node",
    "relationship_context",
    "relationship_state",
    "claim",
    "perception",
    "contradiction_record",
    "merge_record",
}
CHANGE_TARGET_KINDS = NODE_LIKE_TARGET_KINDS | {"relationship"}
CONTRADICTION_STATUSES = {"detected", "needs_clarification", "resolved", "ignored"}
MERGE_STATUSES = {"proposed", "applied", "rejected", "archived", "reverted"}
SAFE_MERGE_LIST_FIELDS = {"aliases", "source_ids", "extraction_run_ids"}
ALIAS_LABELS = {"Person", "Organization", "Animal", "Topic"}
HISTORY_LABELS = {"RelationshipState", "ChangeRecord", "ContradictionRecord", "MergeRecord"}
HIDDEN_LIFECYCLE_STATES = {LifecycleState.ARCHIVED.value, LifecycleState.DELETED.value}
TIMELINE_TIME_FIELDS = (
    "resolved_start",
    "valid_from",
    "source_time",
    "observed_at",
    "received_at",
    "created_at",
)
DISPLAY_METADATA_FIELDS = (
    "address",
    "city",
    "region",
    "country",
    "place_precision",
    "species",
    "breed",
    "sex",
    "status",
    "known_since",
    "circle_type",
    "source_kind",
    "relationship_type",
    "relationship_kind",
    "relationship_detail",
    "closeness",
    "kind",
    "label",
    "label_text",
    "value",
    "provider",
    "external_id",
    "url",
    "category",
    "domain",
)
CONTEXT_FACT_FIELDS = (
    "description",
    "emotional_summary",
    "emotional_valence",
    "emotion_tags",
    "original_user_words",
    "status",
    "closeness",
    "relationship_kind",
    "relationship_detail",
    "known_since",
    "city",
    "country",
    "species",
    "breed",
    "circle_type",
)
