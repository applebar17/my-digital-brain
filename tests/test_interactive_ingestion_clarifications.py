import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from render_uat_refined_ingestion_trace_interactive import (
    _answer_clarifications_from_terminal,
)

from my_digital_brain.chat.clarification import build_clarification_packet
from my_digital_brain.ingestion.contracts import (
    IngestionPendingInteraction,
    IngestionResult,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import IngestionStatus, SourceChannel, SourceType


def test_terminal_answer_runs_next_pipeline_pass_before_checking_next_question() -> None:
    packet = build_clarification_packet(
        frame_id="frame-1",
        origin_state_id="node",
        reason="Amos has no distinguishing detail.",
        questions=[
            {
                "question": "Who is Amos?",
                "options": [{"label": "Amos Vignaroli"}],
            }
        ],
        target_refs=["CANDIDATE_PERSON_001"],
    )
    pending = IngestionResult(
        source_id="source-1",
        status=IngestionStatus.PLANNED,
        pending_interaction=IngestionPendingInteraction(
            stage="node",
            tool_name="ask_clarification",
            clarification_packet=packet.model_dump(mode="json"),
        ),
    )
    completed = IngestionResult(
        source_id="source-1",
        status=IngestionStatus.CANDIDATE_READY,
    )

    class Service:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def process_source(self, source: SourceRecordRef) -> IngestionResult:
            self.calls.append(dict(source.metadata))
            return pending if len(self.calls) == 1 else completed

    service = Service()
    source = SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Amos.",
    )
    route: dict[str, Any] = {"clarification_interactions": []}

    with patch("builtins.input", return_value="Amos Vignaroli"):
        updated_source, result = _answer_clarifications_from_terminal(
            service,
            source,
            base_raw_text=source.raw_text or "",
            result=None,
            route=route,
            max_clarifications=3,
            structured_calls=[],
            tool_calls=[],
            trace_events=[],
        )

    assert len(service.calls) == 2
    assert result is completed
    assert updated_source.metadata["model_facing_history"][-1] == {
        "role": "user",
        "content": "Clarification answer: Amos Vignaroli",
    }
