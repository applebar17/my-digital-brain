from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_ENV_FILE = SRC_ROOT / "my_digital_brain" / ".env"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

logger = logging.getLogger("uat_ingestion_trace")

from my_digital_brain.agentic import (  # noqa: E402
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticStateRunner,
)
from my_digital_brain.ai.client.settings import genai_settings_from_app_settings  # noqa: E402
from my_digital_brain.ai.router import StaticModelRouter  # noqa: E402
from my_digital_brain.ai.session import (  # noqa: E402
    LLMSessionCompleted,
    LLMSessionRequest,
    LLMSessionResult,
)
from my_digital_brain.chat.factory import build_ai_provider  # noqa: E402
from my_digital_brain.config import Settings  # noqa: E402
from my_digital_brain.ingestion import (  # noqa: E402
    GraphWritePlanBuilder,  # noqa: E402
    IngestionService,  # noqa: E402
    LLMResolutionProposalAgent,  # noqa: E402
)
from my_digital_brain.ingestion.contracts import (  # noqa: E402
    CandidateEntity,
    GraphContextPack,
    IngestionResult,
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
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry  # noqa: E402


@dataclass(slots=True)
class CapturedStructuredCall:
    purpose: str | None
    schema: str
    model: str | None
    system_prompt: str
    messages: list[dict[str, Any]]
    output: Any | None = None
    error: dict[str, Any] | None = None


@dataclass(slots=True)
class CapturedToolCall:
    name: str
    arguments: dict[str, Any]
    status: str | None = None
    output: Any | None = None
    error: str | None = None


class TraceStructuredProvider:
    provider_name = "trace_wrapper"

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.provider_name = getattr(delegate, "provider_name", "unknown")
        self.structured_calls: list[CapturedStructuredCall] = []
        self.tool_calls: list[CapturedToolCall] = []

    def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
        call: CapturedStructuredCall | None = None
        if request.output_schema is not None:
            call = CapturedStructuredCall(
                purpose=getattr(request.context, "purpose", None),
                schema=request.output_schema.__name__,
                model=request.model,
                system_prompt=request.system_prompt,
                messages=[
                    message.model_dump(mode="json", exclude_none=True)
                    for message in request.messages
                ],
            )
            self.structured_calls.append(call)

        wrapped_mapping = {
            name: self._capture_tool(name, handler)
            for name, handler in request.tools_mapping.items()
        }
        wrapped_request = request.model_copy(update={"tools_mapping": wrapped_mapping})
        try:
            result = self.delegate.run_session(wrapped_request)
        except Exception as exc:
            if call is not None:
                call.error = {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                }
                logger.exception(
                    "Session failed for schema %s and purpose %s.",
                    call.schema,
                    call.purpose or "unknown",
                )
            raise
        if call is not None and isinstance(result, LLMSessionCompleted):
            call.output = (
                result.parsed.model_dump(mode="json", exclude_none=True)
                if result.parsed is not None
                else None
            )
        return result

    def _capture_tool(self, name: str, handler: Any) -> Any:
        def wrapped(**arguments: Any) -> Any:
            call = CapturedToolCall(name=name, arguments=dict(arguments))
            self.tool_calls.append(call)
            try:
                result = handler(**arguments)
            except Exception as exc:
                call.error = str(exc)
                raise
            call.status = str(getattr(result, "status", "ok"))
            call.output = (
                result.model_dump(mode="json", exclude_none=True)
                if hasattr(result, "model_dump")
                else result
            )
            return result

        return wrapped

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
) -> tuple[IngestionService, TraceStructuredProvider]:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_env_file(env_file, override=override_env)
    settings = Settings()
    graph_context_pack = _ensure_trace_registry(graph_context_pack)
    provider = TraceStructuredProvider(build_ai_provider(settings))
    router = StaticModelRouter(
        settings=genai_settings_from_app_settings(settings),
        provider=settings.normalized_llm_provider,
    )
    runner = AgenticStateRunner(provider=provider, model_router=router)
    service = IngestionService(
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
        resolution_agent=LLMResolutionProposalAgent(
            provider,
            router=router,
            max_tool_calls=settings.ingestion_resolution_max_tool_calls,
        ),
        write_plan_builder=GraphWritePlanBuilder(),
    )
    return service, provider


def _ensure_trace_registry(graph_context_pack: GraphContextPack) -> GraphContextPack:
    if graph_context_pack.reference_registry_snapshot:
        return graph_context_pack
    registry = RunReferenceRegistry(
        graph_scope="uat", run_scope=graph_context_pack.source_id or "uat"
    )
    registry.register_owner("person:owner")
    return graph_context_pack.model_copy(
        update={
            "alias_map": registry.backend_alias_map(),
            "reference_registry_snapshot": registry.snapshot(),
        },
        deep=True,
    )


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
    result: IngestionResult,
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
            [
                candidate.model_dump(mode="json", exclude_none=True)
                for candidate in initial_entities
            ],
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
            [
                candidate.model_dump(mode="json", exclude_none=True)
                for candidate in initial_entities
            ],
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
        f"Generated at: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "Graph/database integrations: disabled",
        "Provider-generated sections are non-deterministic.",
        "",
    ]


def _append_result_summary(lines: list[str], result: IngestionResult) -> None:
    summary = {
        "status": str(result.status),
        "ingestion_stage": result.metadata.get("ingestion_stage"),
        "entity_candidates": len(result.entity_candidates),
        "supplemental_entity_candidates": len(result.supplemental_entity_candidates),
        "relationship_candidates": len(result.relationship_candidates),
        "validation_errors": [
            issue.model_dump(mode="json", exclude_none=True) for issue in result.validation_errors
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
    _append_json_block(lines, "Final Ingestion Result", summary)


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
        _append_json_block(lines, "Messages", call.messages)
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
