from __future__ import annotations

from sqlalchemy import create_engine

from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.rag.models import MEMORY_DOCUMENTS_COLLECTION, VectorRecordData
from my_digital_brain.rag.text_builder import EmbeddingTextBuilder
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import Base


def test_claim_embedding_document_is_low_noise_and_deterministic() -> None:
    builder = EmbeddingTextBuilder()
    claim = _node(
        "Claim",
        {
            "id": "claim-1",
            "text": "Alessandro and I were very close as teenagers.",
            "claim_type": "relationship_memory",
            "original_time_text": "as teenagers",
            "source_ids": ["source-1"],
            "metadata": {"raw_payload": "must not be embedded"},
        },
    )

    document = builder.build_for_node(claim, embedding_model="text-embedding-3-small")

    assert document is not None
    assert document.collection == MEMORY_DOCUMENTS_COLLECTION
    assert document.embedding_scope == "claim_summary"
    assert document.primary_target_id == "claim-1"
    assert document.primary_target_label == "Claim"
    assert document.source_ids == ["source-1"]
    assert document.embedding_model == "text-embedding-3-small"
    assert document.builder_version == "claim_summary.v1"
    assert document.document_checksum.startswith("sha256:")
    assert "Claim: Alessandro and I were very close as teenagers." in document.document
    assert "metadata" not in document.document
    assert "raw_payload" not in document.document


def test_person_place_and_social_circle_skip_bare_labels() -> None:
    builder = EmbeddingTextBuilder()

    assert builder.build_for_node(_node("Person", {"id": "person-1", "display_name": "Marco"})) is None
    assert builder.build_for_node(_node("Place", {"id": "place-1", "name": "Milan"})) is None
    assert (
        builder.build_for_node(_node("SocialCircle", {"id": "circle-1", "name": "Friends"}))
        is None
    )


def test_person_place_and_social_circle_embed_meaningful_context() -> None:
    builder = EmbeddingTextBuilder()
    person = _node(
        "Person",
        {
            "id": "person-1",
            "display_name": "Alessandro",
            "description": "Teenage friend, now low contact.",
            "emotional_summary": "Care mixed with distance.",
            "source_ids": ["source-1"],
        },
    )
    place = _node(
        "Place",
        {
            "id": "place-1",
            "name": "Pizzeria Napoli",
            "city": "Milan",
            "description": "Recurring dinner place connected to memories with Marco.",
        },
    )
    circle = _node(
        "SocialCircle",
        {
            "id": "circle-1",
            "name": "Close friends",
            "circle_type": "user_perceived_group",
            "description": "People the user feels emotionally close to.",
        },
    )

    person_doc = builder.build_for_node(person)
    place_doc = builder.build_for_node(place)
    circle_doc = builder.build_for_node(circle)

    assert person_doc is not None
    assert "Person: Alessandro." in person_doc.document
    assert "Emotional context: Care mixed with distance." in person_doc.document
    assert place_doc is not None
    assert "Place: Pizzeria Napoli." in place_doc.document
    assert "Location: Milan." in place_doc.document
    assert circle_doc is not None
    assert "Social circle: Close friends." in circle_doc.document
    assert "People the user feels emotionally close to." in circle_doc.document


def test_relationship_context_document_keeps_related_targets_and_sources() -> None:
    builder = EmbeddingTextBuilder()
    context = _node(
        "RelationshipContext",
        {
            "id": "relctx-1",
            "description": "Close teenage friendship, now low contact.",
            "relationship_type": "RELATIONSHIP_WITH",
            "relationship_kind": "friend",
            "relationship_detail": "teenage friendship",
            "status": "low_contact",
            "closeness": "formerly_close",
            "emotional_summary": "Care and distance.",
            "source_ids": ["source-1"],
        },
    )
    person = _node("Person", {"id": "person-1", "display_name": "Alessandro"})
    source = _node("Source", {"id": "source-1"})

    document = builder.build_for_node(
        context,
        related_nodes=[person, source],
        relationship_ids=["relationship-1"],
    )

    assert document is not None
    assert document.related_target_ids == ["person-1", "source-1"]
    assert document.source_ids == ["source-1"]
    assert document.relationship_ids == ["relationship-1"]
    assert "Participants: Alessandro." in document.document


def test_checksum_changes_when_informative_text_changes() -> None:
    builder = EmbeddingTextBuilder()
    first = builder.build_for_node(
        _node("ProfileMemory", {"id": "profile-1", "profile_key": "restaurant_preference", "value": "quiet places"}),
    )
    second = builder.build_for_node(
        _node("ProfileMemory", {"id": "profile-1", "profile_key": "restaurant_preference", "value": "lively places"}),
    )

    assert first is not None
    assert second is not None
    assert first.vector_id == second.vector_id
    assert first.document_checksum != second.document_checksum


def test_vector_record_store_upserts_and_lists_by_primary_target(tmp_path) -> None:
    store = _store(tmp_path)
    data = VectorRecordData(
        collection=MEMORY_DOCUMENTS_COLLECTION,
        vector_id="memory_documents:claim_summary:claim-1",
        embedding_scope="claim_summary",
        primary_target_id="claim-1",
        primary_target_label="Claim",
        related_target_ids=["person-1"],
        source_ids=["source-1"],
        relationship_ids=["relationship-1"],
        embedding_model="text-embedding-3-small",
        builder_version="claim_summary.v1",
        document_checksum="sha256:first",
    )

    created = store.upsert(data)
    updated = store.upsert(data.model_copy(update={"document_checksum": "sha256:second"}))
    records = store.list_by_primary_target("claim-1")

    assert created.id == updated.id
    assert updated.document_checksum == "sha256:second"
    assert len(records) == 1
    assert records[0].related_target_ids == ["person-1"]
    assert records[0].source_ids == ["source-1"]
    assert records[0].relationship_ids == ["relationship-1"]


def test_vector_record_store_hides_archived_by_default(tmp_path) -> None:
    store = _store(tmp_path)
    data = VectorRecordData(
        vector_id="memory_documents:event_summary:event-1",
        embedding_scope="event_summary",
        primary_target_id="event-1",
        primary_target_label="Event",
        builder_version="event_summary.v1",
        document_checksum="sha256:event",
    )
    stored = store.upsert(data)

    store.mark_lifecycle_state(
        stored.vector_id,
        "archived",
        vector_store=stored.vector_store,
        collection=stored.collection,
    )

    assert store.list_by_primary_target("event-1") == []
    assert len(store.list_by_primary_target("event-1", include_archived=True)) == 1


def _node(label: str, properties: dict[str, object]) -> NodeSearchResult:
    return NodeSearchResult(label=label, labels=[label], properties=properties)


def _store(tmp_path) -> VectorRecordStore:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'rag.sqlite3').as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return VectorRecordStore(RelationalSessionProvider(engine))
