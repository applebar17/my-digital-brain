from __future__ import annotations

import pytest
from pydantic import ValidationError

from my_digital_brain.clarification.contracts import (
    ClarificationDoubt,
    ClarificationHandoffRequest,
    ClarificationResolutionReport,
    clarification_doubts_schema,
)


def _doubt(**overrides: object) -> dict[str, object]:
    return {
        "doubt_id": "DOUBT_001",
        "doubt": "Amos has no identifying surname.",
        "refs": ["CANDIDATE_PERSON_001"],
        "missing_information": "Full name",
        "why_blocking": "The identity is ambiguous.",
        "evidence_refs": ["CANDIDATE_EVENT_001"],
        **overrides,
    }


def test_handoff_requires_detailed_doubts() -> None:
    request = ClarificationHandoffRequest(
        doubts=[_doubt()],
        invoker_state_id="node",
        invoker_tool_call_id="call-1",
    )

    assert request.doubts[0].refs == ["CANDIDATE_PERSON_001"]
    assert request.invoker_tool_call_id == "call-1"


def test_empty_handoff_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClarificationHandoffRequest(doubts=[], invoker_state_id="node")


def test_resolution_report_accepts_informational_statuses() -> None:
    for status in ("resolved", "partially_resolved", "unresolved", "user_declined", "not_needed"):
        report = ClarificationResolutionReport(
            entries=[{"doubt_id": "DOUBT_001", "status": status}],
        )
        assert report.entries[0].status == status


def test_resolution_report_requires_one_entry_per_handoff_doubt() -> None:
    handoff = ClarificationHandoffRequest(
        doubts=[_doubt(), _doubt(doubt_id="DOUBT_002")],
        invoker_state_id="node",
    )
    report = ClarificationResolutionReport(
        entries=[{"doubt_id": "DOUBT_001", "status": "resolved"}],
    )

    with pytest.raises(ValueError, match="exactly one entry per doubt"):
        report.validate_against(handoff)


def test_tool_schema_requires_doubt_fields_and_no_question_fields() -> None:
    schema = clarification_doubts_schema()
    item = schema["items"]

    assert "doubt" in item["required"]
    assert "evidence_refs" in item["required"]
    assert "question" not in item["properties"]
    assert "options" not in item["properties"]


def test_doubt_contract_preserves_model_facing_refs_without_graph_ids() -> None:
    doubt = ClarificationDoubt.model_validate(_doubt())

    assert doubt.refs == ["CANDIDATE_PERSON_001"]
    assert "person:owner" not in doubt.model_dump_json()
