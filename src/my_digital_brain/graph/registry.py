from __future__ import annotations

from collections.abc import Iterable

from my_digital_brain.graph.exceptions import GraphValidationError

CORE_NODE_LABELS = (
    "Person",
    "Event",
    "Place",
    "Organization",
    "Object",
    "Animal",
    "SocialCircle",
    "Topic",
    "Source",
    "Claim",
    "Perception",
    "RelationshipContext",
    "ProfileMemory",
    "ContactPoint",
    "ExternalReference",
    "ExtractionRun",
    "RelationshipState",
    "ChangeRecord",
    "MemoryLog",
    "MediaAsset",
    "ContradictionRecord",
    "MergeRecord",
)

CORE_RELATIONSHIP_TYPES = (
    "MENTIONED_IN",
    "SUPPORTED_BY",
    "DERIVED_FROM",
    "PARTICIPATED_IN",
    "HAPPENED_AT",
    "ABOUT",
    "RELATED_TO",
    "HAS_CONTACT_POINT",
    "HAS_EXTERNAL_REFERENCE",
    "DESCRIBES_USER",
    "CONTRADICTS",
    "PERCEIVES",
    "PERCEPTION_OF",
    "HAS_RELATIONSHIP_CONTEXT",
    "RELATIONSHIP_WITH",
    "HAS_AFFECTIVE_CONTEXT",
    "KNOWS",
    "WORKS_AT",
    "OWNS",
    "OWNED_BY",
    "CARED_FOR_BY",
    "LIVES_WITH",
    "MEMBER_OF",
    "LOCATED_IN",
    "ALIAS_OF",
    "SAME_AS",
    "CONFIGURES",
    "PRIMARY_CONTACT_FOR",
    "HAS_RELATIONSHIP_STATE",
    "HAS_CHANGE_RECORD",
    "HAS_MEMORY_LOG",
    "INVOLVES",
    "UPDATES_RELATIONSHIP",
    "HAS_MEDIA",
    "DEPICTS",
    "CAPTURED_AT",
    "CAPTURES_EVENT",
    "HAS_CONTRADICTION_RECORD",
    "MERGED_NODE",
    "CANONICAL_NODE",
    "MERGED_INTO",
)

CORE_NODE_LABEL_SET = frozenset(CORE_NODE_LABELS)
CORE_RELATIONSHIP_TYPE_SET = frozenset(CORE_RELATIONSHIP_TYPES)
RELATIONSHIP_DIRECTIONS = frozenset({"in", "out", "both"})


def validate_node_label(label: str) -> str:
    if label not in CORE_NODE_LABEL_SET:
        raise GraphValidationError(f"Unsupported graph node label: {label}")
    return label


def validate_relationship_type(relationship_type: str) -> str:
    if relationship_type not in CORE_RELATIONSHIP_TYPE_SET:
        raise GraphValidationError(f"Unsupported graph relationship type: {relationship_type}")
    return relationship_type


def validate_relationship_direction(direction: str) -> str:
    if direction not in RELATIONSHIP_DIRECTIONS:
        raise GraphValidationError(f"Unsupported relationship direction: {direction}")
    return direction


def primary_core_label(labels: Iterable[str]) -> str:
    for label in labels:
        if label in CORE_NODE_LABEL_SET:
            return label
    raise GraphValidationError(f"No supported graph label found in labels: {list(labels)}")
