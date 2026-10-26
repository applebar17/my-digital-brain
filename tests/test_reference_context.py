"""Functional behavior of the shared run-scoped reference context."""

import pytest

from product.application.references import (
    ReferenceContext,
    ReferenceContextRenderer,
    ReferenceObjectKind,
    ReferenceResolutionStatus,
)


def test_existing_objects_reuse_refs_and_never_render_backend_ids() -> None:
    context = ReferenceContext()
    renderer = ReferenceContextRenderer()

    first = context.register_existing(
        "a55524b1-e481-41e4-8249-73db3d929472",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Jacopo Brutti",
    )
    repeated = context.register_existing(
        "a55524b1-e481-41e4-8249-73db3d929472",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Jacopo Brutti",
    )

    assert repeated.ref == first.ref == "node_0001"
    assert context.resolve(first.ref) == "a55524b1-e481-41e4-8249-73db3d929472"
    for level in (0, 1, 2):
        rendered = renderer.render(context.entries(), level=level)
        assert first.ref in rendered
        assert "a55524b1-e481-41e4-8249-73db3d929472" not in rendered


def test_proposed_reference_keeps_its_identity_after_creation() -> None:
    context = ReferenceContext()
    proposed = context.allocate_proposed(
        object_kind=ReferenceObjectKind.NODE,
        label="Place",
        display_name="Villa Borghese",
    )

    created = context.bind_created(proposed.ref, "place-backend-id")

    assert created.ref == proposed.ref == "node_new_0001"
    assert created.resolution_status == ReferenceResolutionStatus.CREATED
    assert context.resolve(created.ref, expected_kind=ReferenceObjectKind.NODE) == (
        "place-backend-id"
    )


def test_child_delta_preserves_entries_and_private_bindings() -> None:
    child = ReferenceContext()
    person = child.register_existing(
        "person-backend-id",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Elena Rossi",
    )
    relationship = child.register_existing(
        "relationship-backend-id",
        object_kind=ReferenceObjectKind.RELATIONSHIP,
        label="IN_RELATIONSHIP_WITH",
        summary="Elena is in a relationship with Matteo.",
    )

    parent = ReferenceContext()
    parent.merge_delta(child.export_delta([person.ref, relationship.ref]))

    assert parent.entry_for(person.ref) == person
    assert parent.resolve(person.ref) == "person-backend-id"
    assert parent.resolve(
        relationship.ref,
        expected_kind=ReferenceObjectKind.RELATIONSHIP,
    ) == "relationship-backend-id"


def test_child_can_complete_a_parent_proposal_without_changing_its_ref() -> None:
    parent = ReferenceContext()
    proposal = parent.allocate_proposed(
        object_kind=ReferenceObjectKind.NODE,
        label="Event",
        display_name="Sunday lunch",
    )
    child = ReferenceContext()
    child.merge_delta(parent.export_delta([proposal.ref]))

    child.bind_created(proposal.ref, "event-backend-id")
    parent.merge_delta(child.export_delta([proposal.ref]))

    assert parent.entry_for(proposal.ref).resolution_status == (
        ReferenceResolutionStatus.CREATED
    )
    assert parent.resolve(proposal.ref) == "event-backend-id"


def test_owner_projection_uses_readable_identity_or_fallback() -> None:
    renderer = ReferenceContextRenderer()
    named_context = ReferenceContext()
    named_owner = named_context.register_owner(
        "owner-backend-id",
        name="Jacopo",
        surname="Brutti",
    )
    fallback_context = ReferenceContext()
    fallback_owner = fallback_context.register_owner("anonymous-owner-id", name="Jacopo")

    assert named_owner.id == "jacopo_brutti"
    assert "Jacopo Brutti" in renderer.render_owner(named_owner)
    assert fallback_owner.id == "owner"
    assert "Jacopo" in renderer.render_owner(fallback_owner)


def test_snapshot_restores_private_bindings_and_allocation_sequence() -> None:
    original = ReferenceContext()
    first = original.register_existing(
        "first-node-id",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="First person",
    )

    restored = ReferenceContext.from_snapshot(original.snapshot())
    second = restored.register_existing(
        "second-node-id",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Second person",
    )

    assert restored.resolve(first.ref) == "first-node-id"
    assert second.ref == "node_0002"


def test_unknown_or_incompatible_refs_fail_with_recovery_context() -> None:
    context = ReferenceContext()
    node = context.register_existing(
        "person-backend-id",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
    )

    with pytest.raises(ValueError, match="Use an exact reference supplied"):
        context.resolve("node_9999")
    with pytest.raises(ValueError, match="requires relationship"):
        context.resolve(node.ref, expected_kind=ReferenceObjectKind.RELATIONSHIP)
