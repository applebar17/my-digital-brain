from __future__ import annotations

import re

from my_digital_brain.graph.registry import CORE_NODE_LABELS, CORE_RELATIONSHIP_TYPES


def _key(value: str) -> str:
    spaced = re.sub(r"(?<!^)(?=[A-Z])", "_", str(value).strip())
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", spaced).strip("_").lower()
    return normalized


_NODE_LABEL_BY_KEY = {
    **{_key(label): label for label in CORE_NODE_LABELS},
    "people": "Person",
    "human": "Person",
    "contact": "Person",
    "location": "Place",
    "city": "Place",
    "country": "Place",
    "restaurant": "Place",
    "venue": "Place",
    "company": "Organization",
    "business": "Organization",
    "employer": "Organization",
    "item": "Object",
    "thing": "Object",
    "pet": "Animal",
    "group": "SocialCircle",
    "social_group": "SocialCircle",
    "circle": "SocialCircle",
    "family": "SocialCircle",
    "friend_group": "SocialCircle",
    "memory_event": "Event",
    "memory": "Event",
    "fact": "Claim",
    "feeling": "Perception",
    "opinion": "Perception",
}

_RELATIONSHIP_TYPE_BY_KEY = {
    **{_key(relationship_type): relationship_type for relationship_type in CORE_RELATIONSHIP_TYPES},
    "mentioned": "MENTIONED_IN",
    "source": "SUPPORTED_BY",
    "supports": "SUPPORTED_BY",
    "participant": "PARTICIPATED_IN",
    "participates_in": "PARTICIPATED_IN",
    "attended": "PARTICIPATED_IN",
    "met_at": "HAPPENED_AT",
    "at": "HAPPENED_AT",
    "took_place_at": "HAPPENED_AT",
    "happened_in": "HAPPENED_AT",
    "about_ref": "ABOUT",
    "related": "RELATED_TO",
    "relation": "RELATED_TO",
    "knows": "KNOWS",
    "friend": "RELATIONSHIP_WITH",
    "friends": "RELATIONSHIP_WITH",
    "friends_with": "RELATIONSHIP_WITH",
    "friendship": "RELATIONSHIP_WITH",
    "family": "RELATIONSHIP_WITH",
    "sibling": "RELATIONSHIP_WITH",
    "partner": "RELATIONSHIP_WITH",
    "ex_partner": "RELATIONSHIP_WITH",
    "colleague": "RELATIONSHIP_WITH",
    "coworker": "RELATIONSHIP_WITH",
    "works_for": "WORKS_AT",
    "employed_by": "WORKS_AT",
    "owns": "OWNS",
    "owned": "OWNED_BY",
    "cares_for": "CARED_FOR_BY",
    "caregiver": "CARED_FOR_BY",
    "lives_with": "LIVES_WITH",
    "member": "MEMBER_OF",
    "belongs_to": "MEMBER_OF",
    "in_group": "MEMBER_OF",
    "located": "LOCATED_IN",
    "located_at": "LOCATED_IN",
    "located_in": "LOCATED_IN",
    "same": "SAME_AS",
    "same_as": "SAME_AS",
    "alias": "ALIAS_OF",
}


def canonical_node_label(value: str) -> str:
    """Return a graph label for obvious LLM-facing aliases, or the original value."""

    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned
    key = _key(cleaned)
    for candidate_key in _node_label_keys(key):
        if candidate_key in _NODE_LABEL_BY_KEY:
            return _NODE_LABEL_BY_KEY[candidate_key]
    return cleaned


def canonical_relationship_type(value: str) -> str:
    """Return a graph relationship type for obvious LLM-facing aliases, or original."""

    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned
    key = _key(cleaned)
    for candidate_key in _relationship_type_keys(key):
        if candidate_key in _RELATIONSHIP_TYPE_BY_KEY:
            return _RELATIONSHIP_TYPE_BY_KEY[candidate_key]
    return cleaned


def _node_label_keys(key: str) -> tuple[str, ...]:
    candidates = [key]
    for suffix in ("_node", "_entity", "_label"):
        if key.endswith(suffix):
            candidates.append(key[: -len(suffix)])
    return tuple(candidates)


def _relationship_type_keys(key: str) -> tuple[str, ...]:
    candidates = [key]
    for suffix in ("_relationship", "_relation", "_edge", "_type"):
        if key.endswith(suffix):
            candidates.append(key[: -len(suffix)])
    return tuple(candidates)
