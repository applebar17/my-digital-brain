"""Functional contract checks for ingestion-aligned graph node DTOs."""

from pydantic import TypeAdapter

from product.graph import KnowledgeItemKind, NodeCreate, NodeType


def test_graph_contract_validates_all_ingestion_node_subtypes() -> None:
    adapter = TypeAdapter(NodeCreate)
    payloads = [
        {
            "node_type": "person",
            "description": "A friend of the owner.",
            "aliases": ["Jacopo"],
            "display_name": "Jacopo Brutti",
            "given_name": "Jacopo",
            "surname": "Brutti",
            "known_since": None,
        },
        {
            "node_type": "event",
            "description": "A shared trip.",
            "aliases": [],
            "title": "Rome trip",
            "started_at": "last week",
            "ended_at": None,
            "time_precision": "week",
            "organizer_hint": "Organized by the owner's university friends.",
        },
        {
            "node_type": "place",
            "description": "The visited city.",
            "aliases": ["Roma"],
            "name": "Rome",
            "address": None,
            "city": "Rome",
            "region": "Lazio",
            "country": "Italy",
            "place_precision": "city",
            "owner_hint": None,
        },
        {
            "node_type": "organization",
            "description": "The owner's employer.",
            "aliases": [],
            "name": "Example Company",
            "domain": "consulting",
        },
        {
            "node_type": "object",
            "description": "A meaningful book.",
            "aliases": [],
            "name": "The gifted book",
            "category": "book",
            "owner_hint": "The owner received it from a friend.",
        },
        {
            "node_type": "animal",
            "description": "A family pet.",
            "aliases": [],
            "name": "Luna",
            "species": "dog",
            "breed": None,
            "sex": "female",
            "owner_hint": "Lives with the owner's family.",
        },
        {
            "node_type": "social_circle",
            "description": "Friends from university.",
            "aliases": [],
            "name": "University friends",
            "circle_type": "friends",
        },
        {
            "node_type": "knowledge_item",
            "description": "An insight worth retaining.",
            "aliases": [],
            "knowledge_kind": "concept",
            "title": "Connected memory",
            "content": "Memory becomes useful through context and relationships.",
            "attribution": None,
            "reminder_at": None,
        },
    ]

    nodes = [adapter.validate_python(payload) for payload in payloads]

    assert {node.node_type for node in nodes} == set(NodeType)
    assert nodes[-1].knowledge_kind == KnowledgeItemKind.CONCEPT
