from __future__ import annotations

from enum import StrEnum
from typing import Any

from my_digital_brain.ingestion.enums import ExtractionTaskType


class LLMEntityType(StrEnum):
    PERSON = "Person"
    EVENT = "Event"
    PLACE = "Place"
    ORGANIZATION = "Organization"
    OBJECT = "Object"
    ANIMAL = "Animal"
    SOCIAL_CIRCLE = "SocialCircle"
    TOPIC = "Topic"


class LLMRelationshipType(StrEnum):
    RELATIONSHIP_WITH = "RELATIONSHIP_WITH"
    PARTICIPATED_IN = "PARTICIPATED_IN"
    HAPPENED_AT = "HAPPENED_AT"
    ABOUT = "ABOUT"
    WORKS_AT = "WORKS_AT"
    MEMBER_OF = "MEMBER_OF"
    LOCATED_IN = "LOCATED_IN"
    OWNED_BY = "OWNED_BY"
    CARED_FOR_BY = "CARED_FOR_BY"
    LIVES_WITH = "LIVES_WITH"
    RELATED_TO = "RELATED_TO"


class RelationshipKind(StrEnum):
    FRIEND = "friend"
    FAMILY = "family"
    PARTNER = "partner"
    FORMER_PARTNER = "former_partner"
    COLLEAGUE = "colleague"
    CLASSMATE = "classmate"
    ACQUAINTANCE = "acquaintance"


def ontology_prompt_payload() -> dict[str, Any]:
    return {
        "llm_creatable_entity_types": [item.value for item in LLMEntityType],
        "llm_creatable_relationship_types": [item.value for item in LLMRelationshipType],
        "relationship_kinds": [item.value for item in RelationshipKind],
        "relationship_policy": (
            "Use RELATIONSHIP_WITH for social relationships and put the social "
            "class in relationship_kind. Preserve specific wording such as "
            "brother, girlfriend, ex wife, or university friend in "
            "relationship_detail or property_suggestions, never as edge types."
        ),
        "hidden_backend_labels": [
            "Claim",
            "Perception",
            "RelationshipContext",
            "Source",
            "ExtractionRun",
            "ChangeRecord",
            "ContradictionRecord",
            "MergeRecord",
        ],
    }


def task_type_for_entity_type(entity_type: LLMEntityType | str) -> ExtractionTaskType:
    value = entity_type.value if isinstance(entity_type, LLMEntityType) else str(entity_type)
    mapping = {
        LLMEntityType.PERSON.value: ExtractionTaskType.PERSON,
        LLMEntityType.EVENT.value: ExtractionTaskType.EVENT,
        LLMEntityType.PLACE.value: ExtractionTaskType.PLACE,
        LLMEntityType.ORGANIZATION.value: ExtractionTaskType.ORGANIZATION,
        LLMEntityType.OBJECT.value: ExtractionTaskType.OBJECT,
        LLMEntityType.ANIMAL.value: ExtractionTaskType.ANIMAL,
        LLMEntityType.SOCIAL_CIRCLE.value: ExtractionTaskType.SOCIAL_CIRCLE,
        LLMEntityType.TOPIC.value: ExtractionTaskType.TOPIC,
    }
    return mapping[value]
