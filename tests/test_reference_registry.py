from __future__ import annotations

import pytest

from my_digital_brain.ingestion import RunReferenceRegistry
from my_digital_brain.ingestion.contracts import ReferenceObjectKind


def _registry() -> RunReferenceRegistry:
    return RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")


def test_registry_allocates_uppercase_aliases_and_reuses_internal_ids() -> None:
    registry = _registry()

    first = registry.register_existing(
        "person-matteo",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    )
    second = registry.register_existing(
        "rel:RELATIONSHIP_WITH:person-matteo",
        object_kind=ReferenceObjectKind.EDGE,
        label="RELATIONSHIP_WITH",
    )

    assert first == "NODE_000001"
    assert second == "REL_000001"
    assert registry.register_existing(
        "person-matteo",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    ) == first
    assert registry.resolve(first) == "person-matteo"
    assert registry.alias_for_internal("person-matteo") == first


def test_owner_is_reserved_and_resolved_only_as_owner() -> None:
    registry = _registry()

    assert registry.register_owner("person:owner") == "OWNER"
    assert registry.resolve("OWNER", expected_kind=ReferenceObjectKind.NODE) == "person:owner"
    with pytest.raises(ValueError, match="model-facing aliases"):
        registry.register_existing(
            "OWNER",
            object_kind=ReferenceObjectKind.NODE,
            label="Person",
        )


def test_proposal_is_unbound_until_backend_binding() -> None:
    registry = _registry()
    registry.register_proposal(
        "CANDIDATE_PERSON_001",
        label="Person",
        display_label="Marco",
    )

    with pytest.raises(ValueError, match="not bound"):
        registry.resolve("CANDIDATE_PERSON_001")

    assert registry.bind_proposal("CANDIDATE_PERSON_001", "new-person") == "NODE_000001"
    assert registry.resolve("CANDIDATE_PERSON_001") == "new-person"
    assert registry.resolve("NODE_000001") == "new-person"


def test_local_context_aliases_are_allocated_by_the_registry() -> None:
    registry = _registry()

    first = registry.register_local(
        object_kind=ReferenceObjectKind.CONTEXT,
        label="RelationshipContext",
    )
    second = registry.register_local(
        object_kind=ReferenceObjectKind.CONTEXT,
        label="RelationshipContext",
    )

    assert (first, second) == ("CONTEXT_000001", "CONTEXT_000002")
    assert all("backend_id" not in item for item in registry.model_facing_entries())


def test_registry_rejects_kind_collisions_and_unknown_references() -> None:
    registry = _registry()
    registry.register_existing(
        "shared-id",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    )

    with pytest.raises(ValueError, match="multiple object kinds"):
        registry.register_existing(
            "shared-id",
            object_kind=ReferenceObjectKind.MEMORY,
            label="MemoryLog",
        )
    with pytest.raises(ValueError, match="Unknown"):
        registry.resolve("NODE_999999")


def test_registry_snapshot_round_trip_preserves_scope_and_counters() -> None:
    registry = _registry()
    registry.register_owner("person:owner")
    registry.register_existing(
        "person-marco",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    )
    registry.register_proposal("CANDIDATE_PERSON_001", label="Person")

    restored = RunReferenceRegistry.from_snapshot(registry.snapshot())

    assert restored.resolve("OWNER") == "person:owner"
    assert restored.resolve("NODE_000001") == "person-marco"
    assert restored.register_existing(
        "person-lorenzo",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    ) == "NODE_000002"
    assert restored.model_facing_entries()[-1] == {
        "ref": "OWNER",
        "object_kind": "node",
        "status": "existing",
        "label": "Person",
    }


def test_model_facing_projection_redacts_internal_ids_and_scopes() -> None:
    registry = _registry()
    registry.register_owner("person:owner")
    registry.register_existing(
        "uuid-marco",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_label="Marco Bianchi",
    )

    payload = registry.model_facing_entries()

    assert all("backend_id" not in entry for entry in payload)
    assert all("graph_scope" not in entry for entry in payload)
    assert all("session_scope" not in entry for entry in payload)
    assert "uuid-marco" not in str(payload)
    assert "person:owner" not in str(payload)


def test_snapshot_scope_cannot_be_reused_by_another_run() -> None:
    registry = _registry()
    registry.register_existing(
        "person-marco",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    )

    with pytest.raises(ValueError, match="run scope"):
        RunReferenceRegistry.from_snapshot(registry.snapshot(), run_scope="run-2")
