from __future__ import annotations

from datetime import UTC, datetime

from my_digital_brain.ingestion.contracts import (
    IngestionResult,
    IngestionSessionSnapshot,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import IngestionStatus


class InMemoryIngestionProcessStore:
    """Small process-state store for tests and local/private runs.

    A relational implementation can persist the same snapshots into the existing
    `source_records` and `ingestion_sessions` tables.
    """

    def __init__(self) -> None:
        self.sources: dict[str, SourceRecordRef] = {}
        self.sessions: dict[str, IngestionSessionSnapshot] = {}

    def save_source(self, source: SourceRecordRef) -> SourceRecordRef:
        self.sources[source.source_id] = source
        return source

    def record_result(
        self,
        result: IngestionResult,
        *,
        expires_at: datetime | None = None,
    ) -> IngestionSessionSnapshot:
        snapshot = IngestionSessionSnapshot(
            session_id=result.ingestion_id,
            source_id=result.source_id,
            status=result.status,
            pending_question=(
                result.clarification.question if result.clarification is not None else None
            ),
            pending_questions=[item.question for item in result.clarifications],
            candidate_graph_snapshot=(
                result.candidate_graph.model_dump(mode="json", exclude_none=True)
                if result.candidate_graph is not None
                else {}
            ),
            write_plan_snapshot=(
                result.write_plan.model_dump(mode="json", exclude_none=True)
                if result.write_plan is not None
                else {}
            ),
            expires_at=expires_at,
            metadata=dict(result.metadata),
        )
        self.sessions[snapshot.session_id] = snapshot
        return snapshot

    def get_session(self, session_id: str) -> IngestionSessionSnapshot | None:
        return self.sessions.get(session_id)

    def expire_pending(self, now: datetime | None = None) -> list[str]:
        current_time = now or datetime.now(UTC)
        expired_ids: list[str] = []
        for session_id, snapshot in list(self.sessions.items()):
            if snapshot.status != IngestionStatus.NEEDS_CLARIFICATION:
                continue
            if snapshot.expires_at is None or snapshot.expires_at > current_time:
                continue
            snapshot.status = IngestionStatus.FAILED
            snapshot.metadata["expired"] = True
            expired_ids.append(session_id)
        return expired_ids
