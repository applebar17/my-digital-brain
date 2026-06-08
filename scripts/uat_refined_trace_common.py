from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_ENV_FILE = SRC_ROOT / "my_digital_brain" / ".env"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

logger = logging.getLogger("uat_refined_trace")

from my_digital_brain.agentic import (  # noqa: E402
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticStateRunner,
)
from my_digital_brain.ai.client.settings import genai_settings_from_app_settings  # noqa: E402
from my_digital_brain.ai.router import StaticModelRouter  # noqa: E402
from my_digital_brain.chat.factory import build_ai_provider  # noqa: E402
from my_digital_brain.config import Settings  # noqa: E402
from my_digital_brain.ingestion import RefinedIngestionService  # noqa: E402
from my_digital_brain.ingestion.contracts import (  # noqa: E402
    CandidateEntity,
    GraphContextPack,
    RefinedIngestionResult,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import SourceChannel, SourceType  # noqa: E402
from my_digital_brain.ingestion.extractors import (  # noqa: E402
    ClaimExtractor,
    EntityExtractor,
    MetadataPatchExtractor,
    PerceptionExtractor,
    RelationshipContextExtractor,
    RelationshipExtractor,
)


@dataclass(slots=True)
class CapturedStructuredCall:
    purpose: str | None
    schema: str
    model: str | None
    system_prompt: str
    input_message: Any
    output: Any | None = None
    error: dict[str, Any] | None = None


class TraceStructuredProvider:
    provider_name = "trace_wrapper"

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.provider_name = getattr(delegate, "provider_name", "unknown")
        self.structured_calls: list[CapturedStructuredCall] = []

    def generate_structured(self, request: Any) -> Any:
        call = CapturedStructuredCall(
            purpose=getattr(request.context, "purpose", None),
            schema=request.output_schema.__name__,
            model=request.model,
            system_prompt=request.system_prompt,
            input_message=request.input_message,
        )
        self.structured_calls.append(call)
        try:
            result = self.delegate.generate_structured(request)
        except Exception as exc:
            call.error = {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
            logger.exception(
                "Structured call failed for schema %s and purpose %s.",
                call.schema,
                call.purpose or "unknown",
            )
            raise
        call.output = result.parsed.model_dump(mode="json", exclude_none=True)
        return result

    def generate_chat(self, request: Any) -> Any:
        return self.delegate.generate_chat(request)

    def generate_chat_with_tools(self, request: Any, **kwargs: Any) -> Any:
        return self.delegate.generate_chat_with_tools(request, **kwargs)

    def embed(self, request: Any) -> Any:
        return self.delegate.embed(request)

    def transcribe(self, request: Any) -> Any:
        return self.delegate.transcribe(request)


class StaticGraphContextBuilder:
    def __init__(self, pack: GraphContextPack) -> None:
        self.pack = pack

    def build(self, source: SourceRecordRef) -> GraphContextPack:
        return self.pack.model_copy(update={"source_id": source.source_id}, deep=True)


def build_trace_service(
    *,
    graph_context_pack: GraphContextPack,
    env_file: Path | None = DEFAULT_ENV_FILE,
    override_env: bool = False,
) -> tuple[RefinedIngestionService, TraceStructuredProvider]:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_env_file(env_file, override=override_env)
    settings = Settings()
    provider = TraceStructuredProvider(build_ai_provider(settings))
    router = StaticModelRouter(
        settings=genai_settings_from_app_settings(settings),
        provider=settings.normalized_llm_provider,
    )
    runner = AgenticStateRunner(provider=provider, model_router=router)
    service = RefinedIngestionService(
        reasoning_service=AgenticReasoningService(runner),
        planning_service=AgenticPlanningService(runner),
        graph_context_builder=StaticGraphContextBuilder(graph_context_pack),
        entity_extractors=[EntityExtractor(provider, router=router)],
        relationship_extractors=[
            RelationshipExtractor(provider, router=router),
            RelationshipContextExtractor(provider, router=router),
            PerceptionExtractor(provider, router=router),
            ClaimExtractor(provider, router=router),
            MetadataPatchExtractor(provider, router=router),
        ],
    )
    return service, provider


def load_env_file(path: Path | None, *, override: bool = False) -> Path | None:
    if path is None:
        return None
    path = path.expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return None
    values = _read_env_values(path)
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return path


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def source_from_file(path: Path, *, timezone_name: str) -> SourceRecordRef:
    text = path.read_text(encoding="utf-8")
    return SourceRecordRef(
        source_id=f"uat:{path.as_posix()}",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text=text,
        metadata={"timezone": timezone_name, "uat_input_path": path.as_posix()},
    )


def load_graph_context_pack(path: Path | None, *, source_id: str) -> GraphContextPack:
    if path is None:
        return GraphContextPack(
            source_id=source_id,
            compact_summary="No graph context supplied for this local UAT run.",
            retrieval_strategy="uat_empty_graph_context",
            notes=[
                "This report intentionally runs without graph/database integrations.",
            ],
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    pack = GraphContextPack.model_validate(payload)
    return pack.model_copy(update={"source_id": source_id}, deep=True)


def load_entity_candidates(path: Path, *, source: SourceRecordRef) -> list[CandidateEntity]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("candidates", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("--entities must be a JSON list or an object with a candidates list.")
    candidates: list[CandidateEntity] = []
    for item in items:
        candidate = CandidateEntity.model_validate(item)
        if not candidate.source_refs and not candidate.evidence_refs:
            candidate = candidate.model_copy(update={"source_refs": [source.source_id]})
        candidates.append(candidate)
    return candidates


def write_report(
    output: Path,
    *,
    title: str,
    source: SourceRecordRef,
    route: dict[str, Any],
    result: RefinedIngestionResult,
    structured_calls: list[CapturedStructuredCall],
    initial_entities: list[CandidateEntity] | None = None,
) -> None:
    lines = _base_report_lines(title)
    _append_text_block(lines, "User Request", source.raw_text or source.content_ref or "")
    _append_json_block(lines, "Routing", route)
    if initial_entities is not None:
        _append_json_block(
            lines,
            "Initial Predefined Entity Candidates",
            [candidate.model_dump(mode="json", exclude_none=True) for candidate in initial_entities],
        )
    _append_result_summary(lines, result)
    _append_structured_calls(lines, structured_calls)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_failure_report(
    output: Path,
    *,
    title: str,
    source: SourceRecordRef,
    route: dict[str, Any],
    error: Exception,
    structured_calls: list[CapturedStructuredCall],
    initial_entities: list[CandidateEntity] | None = None,
) -> None:
    lines = _base_report_lines(title)
    _append_text_block(lines, "User Request", source.raw_text or source.content_ref or "")
    _append_json_block(lines, "Routing", route)
    if initial_entities is not None:
        _append_json_block(
            lines,
            "Initial Predefined Entity Candidates",
            [candidate.model_dump(mode="json", exclude_none=True) for candidate in initial_entities],
        )
    _append_json_block(
        lines,
        "Execution Error",
        {
            "error_type": error.__class__.__name__,
            "message": str(error),
        },
    )
    _append_structured_calls(lines, structured_calls)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _base_report_lines(title: str) -> list[str]:
    return [
        title,
        "=" * len(title),
        "",
        f"Generated at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        "Graph/database integrations: disabled",
        "Provider-generated sections are non-deterministic.",
        "",
    ]


def _append_result_summary(lines: list[str], result: RefinedIngestionResult) -> None:
    summary = {
        "status": str(result.status),
        "refined_stage": result.metadata.get("refined_stage"),
        "entity_candidates": len(result.entity_candidates),
        "supplemental_entity_candidates": len(result.supplemental_entity_candidates),
        "relationship_candidates": len(result.relationship_candidates),
        "validation_errors": [
            issue.model_dump(mode="json", exclude_none=True)
            for issue in result.validation_errors
        ],
        "missing_entities": (
            [
                item.model_dump(mode="json", exclude_none=True)
                for item in result.relationship_plan.missing_entities
            ]
            if result.relationship_plan is not None
            else []
        ),
        "resolved_entity_map": (
            result.resolved_entity_map.model_dump(mode="json", exclude_none=True)
            if result.resolved_entity_map is not None
            else None
        ),
        "final_candidate_graph": (
            result.candidate_graph.model_dump(mode="json", exclude_none=True)
            if result.candidate_graph is not None
            else None
        ),
    }
    _append_json_block(lines, "Final Refined Ingestion Result", summary)


def _append_structured_calls(
    lines: list[str],
    structured_calls: list[CapturedStructuredCall],
) -> None:
    for index, call in enumerate(structured_calls, start=1):
        title = f"Structured Call {index}: {call.schema}"
        lines.extend([title, "-" * len(title), ""])
        lines.append(f"Purpose: {call.purpose or 'unknown'}")
        lines.append(f"Model: {call.model or 'default route'}")
        lines.append("")
        _append_text_block(lines, "System Prompt", call.system_prompt)
        _append_json_block(lines, "Input", call.input_message)
        if call.error is not None:
            _append_json_block(lines, "Error / Diagnostics", call.error)
        _append_json_block(lines, "Output", call.output)


def _append_text_block(lines: list[str], title: str, text: str) -> None:
    lines.extend([title, "~" * len(title), ""])
    lines.append(text.strip() or "(empty)")
    lines.append("")


def _append_json_block(lines: list[str], title: str, payload: Any) -> None:
    lines.extend([title, "~" * len(title), ""])
    lines.append(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    lines.append("")
