from __future__ import annotations

import pytest
from pydantic import ValidationError

from my_digital_brain.ingestion.contracts import (
    EntityLookupCandidate,
    EntityLookupContextPacket,
    EntityLookupRelatedContext,
    EntityLookupRequest,
    EntityLookupResult,
    EntityResolutionAction,
    EntityResolutionProposal,
    IdentityLookupStatus,
    IdentityMatchKind,
    ReferenceObjectKind,
    ReferenceRegistryEntry,
    ReferenceStatus,
)


def _candidate(ref: str = "NODE_000001") -> EntityLookupCandidate:
    return EntityLookupCandidate(
        ref=ref,
        label="Person",
        display_name="Marco Bianchi",
        aliases=["Marco"],
        match_kind=IdentityMatchKind.NAME_TOKEN,
        related_context=EntityLookupRelatedContext(
            relationship_summaries=["university friend"],
            relevant_memory_summaries=["Attended university together"],
        ),
    )


def test_lookup_request_is_backend_derived_from_candidate_fields() -> None:
    request = EntityLookupRequest(
        candidate_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        display_name="Marco",
        aliases=["Marc"],
        typed_identity_values={"name": ["Marco"]},
    )

    assert request.max_candidates == 5
    assert request.typed_identity_values == {"name": ["Marco"]}


def test_lookup_request_rejects_non_candidate_reference() -> None:
    with pytest.raises(ValidationError, match="CANDIDATE"):
        EntityLookupRequest(
            candidate_ref="NODE_000001",
            entity_type="Person",
        )


def test_lookup_result_statuses_have_consistent_candidate_counts() -> None:
    empty = EntityLookupResult(
        candidate_ref="CANDIDATE_PERSON_001",
        status=IdentityLookupStatus.NO_CANDIDATES,
    )
    one = EntityLookupResult(
        candidate_ref="CANDIDATE_PERSON_001",
        status=IdentityLookupStatus.ONE_CANDIDATE,
        candidates=[_candidate()],
    )

    assert empty.candidates == []
    assert len(one.candidates) == 1

    with pytest.raises(ValidationError, match="exactly one"):
        EntityLookupResult(
            candidate_ref="CANDIDATE_PERSON_001",
            status=IdentityLookupStatus.ONE_CANDIDATE,
        )


def test_context_packet_requires_matching_candidate_reference() -> None:
    result = EntityLookupResult(
        candidate_ref="CANDIDATE_PERSON_002",
        status=IdentityLookupStatus.NO_CANDIDATES,
    )

    with pytest.raises(ValidationError, match="target the packet candidate"):
        EntityLookupContextPacket(
            candidate_ref="CANDIDATE_PERSON_001",
            entity_type="Person",
            lookup=result,
        )


def test_resolution_proposal_requires_existing_target_only_for_attachment() -> None:
    proposal = EntityResolutionProposal(
        candidate_ref="CANDIDATE_PERSON_001",
        action=EntityResolutionAction.ATTACH_TO_EXISTING,
        target_ref="NODE_000001",
        reason="The university context identifies Marco Bianchi.",
    )
    new_node = EntityResolutionProposal(
        candidate_ref="CANDIDATE_PERSON_002",
        action=EntityResolutionAction.CREATE_NEW,
        reason="No existing candidate matches.",
    )

    assert proposal.target_ref == "NODE_000001"
    assert new_node.target_ref is None

    with pytest.raises(ValidationError, match="requires target_ref"):
        EntityResolutionProposal(
            candidate_ref="CANDIDATE_PERSON_001",
            action=EntityResolutionAction.ATTACH_TO_EXISTING,
            reason="Missing target.",
        )

    with pytest.raises(ValidationError, match="allowed only"):
        EntityResolutionProposal(
            candidate_ref="CANDIDATE_PERSON_001",
            action=EntityResolutionAction.CREATE_NEW,
            target_ref="NODE_000001",
            reason="Conflicting action.",
        )


def test_resolution_proposal_rejects_invented_or_proposed_target() -> None:
    for target_ref in ("person:raw-id", "CANDIDATE_PERSON_002"):
        with pytest.raises(ValidationError, match="OWNER or NODE"):
            EntityResolutionProposal(
                candidate_ref="CANDIDATE_PERSON_001",
                action=EntityResolutionAction.ATTACH_TO_EXISTING,
                target_ref=target_ref,
                reason="Invalid target.",
            )


def test_reference_registry_separates_backend_and_model_facing_data() -> None:
    entry = ReferenceRegistryEntry(
        ref="NODE_000001",
        object_kind=ReferenceObjectKind.NODE,
        status=ReferenceStatus.EXISTING,
        label="Person",
        backend_id="person:marco-bianchi",
        graph_scope="graph-1",
        session_scope="session-1",
        display_label="Marco Bianchi",
        aliases=["Marco"],
    )

    model_payload = entry.model_facing_payload()

    assert model_payload["ref"] == "NODE_000001"
    assert model_payload["display_label"] == "Marco Bianchi"
    assert "backend_id" not in model_payload
    assert "graph_scope" not in model_payload
    assert "session_scope" not in model_payload


def test_owner_registry_entry_is_reserved_and_structurally_protected() -> None:
    owner = ReferenceRegistryEntry(
        ref="OWNER",
        object_kind=ReferenceObjectKind.NODE,
        status=ReferenceStatus.EXISTING,
        label="Person",
        backend_id="person:owner",
        graph_scope="graph-1",
        session_scope="session-1",
        is_owner=True,
    )

    assert owner.model_facing_payload() == {
        "ref": "OWNER",
        "object_kind": "node",
        "status": "existing",
        "label": "Person",
    }

    with pytest.raises(ValidationError, match="owner node"):
        ReferenceRegistryEntry(
            ref="OWNER",
            object_kind=ReferenceObjectKind.NODE,
            status=ReferenceStatus.EXISTING,
            label="Person",
            backend_id="person:owner",
            graph_scope="graph-1",
            session_scope="session-1",
        )


def test_proposed_reference_cannot_carry_backend_identity() -> None:
    with pytest.raises(ValidationError, match="cannot contain a backend ID"):
        ReferenceRegistryEntry(
            ref="CANDIDATE_PERSON_001",
            object_kind=ReferenceObjectKind.NODE,
            status=ReferenceStatus.PROPOSED,
            label="Person",
            backend_id="person:new",
            graph_scope="graph-1",
            session_scope="session-1",
        )
