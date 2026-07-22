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


def test_terminal_answer_resumes_the_paused_session_without_rerunning_pipeline() -> None:
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
            self.process_calls: list[dict[str, Any]] = []
            self.resume_calls: list[tuple[SourceRecordRef, IngestionResult, str]] = []

        def process_source(self, source: SourceRecordRef) -> IngestionResult:
            self.process_calls.append(dict(source.metadata))
            return pending

        def resume_pending(
            self,
            source: SourceRecordRef,
            result: IngestionResult,
            answer: str,
        ) -> IngestionResult:
            self.resume_calls.append((source, result, answer))
            return completed

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
            structured_calls=[],
            tool_calls=[],
            trace_events=[],
        )

    assert len(service.process_calls) == 1
    assert len(service.resume_calls) == 1
    assert service.resume_calls[0][2] == "Amos Vignaroli"
    assert result is completed
    assert updated_source.metadata["model_facing_history"][-1] == {
        "role": "user",
        "content": "Clarification answer: Amos Vignaroli",
    }
