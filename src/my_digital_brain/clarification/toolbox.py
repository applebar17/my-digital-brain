"""Read-only clarification context and semantic question tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.ai.models import ToolResult

from .context_projection import project_entity_detail, project_relationship, relationship_matches
from .contracts import (
    ClarificationKind,
    ClarificationModel,
    ClarificationPacket,
    ClarificationResponseMode,
    option_summaries_required,
)
from .interaction import build_clarification_packet

DEFAULT_LOOKUP_LIMIT = 5
MAX_LOOKUP_LIMIT = 10
DEFAULT_CONTEXT_LIMIT = 5
MAX_CONTEXT_LIMIT = 20


class ClarificationQuestionOption(ClarificationModel):
    """LLM-supplied option data; the backend assigns its option id."""

    label: str = Field(min_length=1)
    summary: str | None = Field(default=None, max_length=160)
    target_ref: str | None = None
    recommended: bool = False


class ClarificationQuestionRequest(ClarificationModel):
    question: str = Field(min_length=1)
    kind: ClarificationKind
    reason: str = Field(min_length=1)
    target_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    options: list[ClarificationQuestionOption] = Field(default_factory=list, max_length=5)
    allow_custom_answer: bool = True

    @model_validator(mode="after")
    def _validate_option_summaries(self) -> ClarificationQuestionRequest:
        if option_summaries_required(self.kind):
            missing_summaries = [
                option.label
                for option in self.options
                if not option.summary or not option.summary.strip()
            ]
            if missing_summaries:
                raise ValueError(
                    f"Disambiguation options require brief summaries: {missing_summaries}."
                )
        return self


@dataclass(slots=True)
class ClarificationToolService:
    """Backend boundary for the clarification agent's read and question tools."""

    graph_service: Any | None
    reference_registry: Any | None
    owner_manager: Any | None = None
    owner_graph_node_id: str | None = None

    def lookup_candidates(
        self,
        *,
        candidate_ref: str,
        entity_type: str,
        display_name: str | None = None,
        aliases: list[str] | None = None,
        typed_identity_values: dict[str, list[str]] | None = None,
        max_candidates: int = DEFAULT_LOOKUP_LIMIT,
    ) -> ToolResult:
        try:
            from my_digital_brain.ingestion.contracts import (
                EntityLookupRequest,
                ReferenceObjectKind,
            )
            from my_digital_brain.ingestion.identity_lookup import (
                DeterministicIdentityLookupService,
            )

            registry = self._registry()
            self._require_ref(
                candidate_ref,
                registry,
                ReferenceObjectKind.NODE,
                allow_proposed=True,
            )
            limit = _bounded_limit(max_candidates, MAX_LOOKUP_LIMIT, DEFAULT_LOOKUP_LIMIT)
            request = EntityLookupRequest(
                candidate_ref=candidate_ref,
                entity_type=entity_type,
                display_name=display_name,
                aliases=list(aliases or []),
                typed_identity_values=dict(typed_identity_values or {}),
                max_candidates=limit,
            )
            if self.graph_service is None:
                return _error(
                    "lookup_candidates",
                    "missing_dependency",
                    "Graph service is not configured.",
                )
            result = DeterministicIdentityLookupService(
                graph_service=self.graph_service,
                owner_manager=self.owner_manager,
                owner_graph_node_id=self.owner_graph_node_id,
                max_candidates=limit,
            ).lookup(request, registry=registry)
            return ToolResult(
                status="ok",
                output="Structured candidate lookup completed.",
                data={"operation": "lookup_candidates", "result": result.model_dump(mode="json")},
            )
        except Exception as exc:
            return _error("lookup_candidates", "invalid_lookup_request", str(exc), retryable=True)

    def get_candidate_context(
        self,
        *,
        refs: list[str],
        include_relationships: bool = True,
        include_evidence: bool = True,
        limit: int = DEFAULT_CONTEXT_LIMIT,
    ) -> ToolResult:
        try:
            from my_digital_brain.ingestion.contracts import ReferenceObjectKind

            registry = self._registry()
            refs = _unique_refs(refs)
            if not refs:
                raise ValueError("At least one model-facing ref is required.")
            if len(refs) > MAX_CONTEXT_LIMIT:
                raise ValueError(f"At most {MAX_CONTEXT_LIMIT} refs may be requested.")
            if self.graph_service is None:
                return _error(
                    "get_candidate_context",
                    "missing_dependency",
                    "Graph service is not configured.",
                )
            bounded = _bounded_limit(limit, MAX_CONTEXT_LIMIT, DEFAULT_CONTEXT_LIMIT)
            contexts = []
            for ref in refs:
                node_id = self._require_ref(ref, registry, ReferenceObjectKind.NODE)
                detail = self.graph_service.get_entity_detail(
                    node_id,
                    include_history=False,
                    include_archived=False,
                    limit=bounded,
                )
                contexts.append(
                    project_entity_detail(
                        detail,
                        registry,
                        graph_service=self.graph_service,
                        include_relationships=include_relationships,
                        include_evidence=include_evidence,
                        limit=bounded,
                    )
                )
            return ToolResult(
                status="ok",
                output="Candidate context lookup completed.",
                data={"operation": "get_candidate_context", "contexts": contexts},
            )
        except Exception as exc:
            return _error(
                "get_candidate_context",
                "invalid_context_request",
                str(exc),
                retryable=True,
            )

    def get_relationship_context(
        self,
        *,
        from_ref: str,
        to_ref: str,
        relationship_type: str | None = None,
        limit: int = DEFAULT_CONTEXT_LIMIT,
    ) -> ToolResult:
        try:
            from my_digital_brain.ingestion.contracts import ReferenceObjectKind

            registry = self._registry()
            from_id = self._require_ref(from_ref, registry, ReferenceObjectKind.NODE)
            to_id = self._require_ref(to_ref, registry, ReferenceObjectKind.NODE)
            if self.graph_service is None:
                return _error(
                    "get_relationship_context",
                    "missing_dependency",
                    "Graph service is not configured.",
                )
            relationships = self.graph_service.get_node_relationships(
                from_id,
                relationship_type=relationship_type,
                direction="both",
                limit=_bounded_limit(limit, MAX_CONTEXT_LIMIT, DEFAULT_CONTEXT_LIMIT),
            )
            projected = [
                project_relationship(item, registry)
                for item in relationships
                if relationship_matches(item, from_id, to_id)
            ]
            return ToolResult(
                status="ok",
                output="Relationship context lookup completed.",
                data={
                    "operation": "get_relationship_context",
                    "from_ref": from_ref,
                    "to_ref": to_ref,
                    "relationships": projected,
                },
            )
        except Exception as exc:
            return _error(
                "get_relationship_context",
                "invalid_relationship_context_request",
                str(exc),
                retryable=True,
            )

    def build_question(
        self,
        *,
        tool_name: str,
        request: dict[str, Any],
        frame_id: str,
        tool_call_id: str | None,
        origin_state_id: str,
    ) -> ToolResult:
        try:
            question_request = ClarificationQuestionRequest.model_validate(request)
            registry = self._registry()
            refs = [*question_request.target_refs, *question_request.evidence_refs]
            for option in question_request.options:
                if option.target_ref:
                    refs.append(option.target_ref)
            for ref in _unique_refs(refs):
                self._require_ref(ref, registry, allow_proposed=True)
            response_mode = _response_mode_for_tool(tool_name)
            packet = build_clarification_packet(
                frame_id=frame_id,
                origin_state_id=origin_state_id,
                reason=question_request.reason,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                target_refs=question_request.target_refs,
                allowed_refs=set(_registry_refs(registry)),
                questions=[
                    {
                        "question": question_request.question,
                        "kind": _enum_value(question_request.kind),
                        "response_mode": _enum_value(response_mode),
                        "target_refs": question_request.target_refs,
                        "evidence_refs": question_request.evidence_refs,
                        "allow_custom_answer": question_request.allow_custom_answer,
                        "options": [
                            option.model_dump(mode="json") for option in question_request.options
                        ],
                    },
                ],
            )
            return _pending_question_result(packet)
        except Exception as exc:
            return _error(tool_name, "invalid_question_request", str(exc), retryable=True)

    def _registry(self) -> Any:
        if self.reference_registry is None:
            raise ValueError("The active run reference registry is not configured.")
        return self.reference_registry

    def _require_ref(
        self,
        ref: str,
        registry: Any,
        expected_kind: Any | None = None,
        allow_proposed: bool = False,
    ) -> str:
        if not ref or ":" in ref or len(ref) > 120:
            raise ValueError(f"Invalid model-facing reference: {ref}")
        entry = registry.entry_for(ref)
        if allow_proposed and str(entry.status) == "proposed":
            if expected_kind is not None and entry.object_kind != expected_kind:
                raise ValueError(f"Reference has an unexpected object kind: {ref}")
            return ref
        return registry.resolve(ref, expected_kind=expected_kind)


def _response_mode_for_tool(tool_name: str) -> ClarificationResponseMode:
    modes = {
        "pick_one": ClarificationResponseMode.SINGLE_CHOICE,
        "pick_many": ClarificationResponseMode.MULTIPLE_CHOICE,
        "confirm": ClarificationResponseMode.CONFIRMATION,
        "ask_text": ClarificationResponseMode.FREE_TEXT,
        "ask_text_or_audio": ClarificationResponseMode.TEXT_OR_AUDIO,
    }
    try:
        return modes[tool_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported clarification question tool: {tool_name}") from exc


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _pending_question_result(packet: ClarificationPacket) -> ToolResult:
    return ToolResult(
        status="pending",
        output="A canonical clarification packet is ready for the channel.",
        data={
            "operation": packet.tool_name,
            "clarification_packet": packet.model_dump(mode="json", exclude_none=True),
            "interaction_group": "clarification_questions",
        },
    )


def _registry_refs(registry: Any) -> list[str]:
    return [str(entry["ref"]) for entry in registry.snapshot().get("entries", [])]


def _node_kind() -> Any:
    from my_digital_brain.ingestion.contracts import ReferenceObjectKind

    return ReferenceObjectKind.NODE


def _unique_refs(refs: list[str]) -> list[str]:
    return list(dict.fromkeys(str(ref).strip() for ref in refs if str(ref).strip()))


def _bounded_limit(value: int, maximum: int, default: int) -> int:
    normalized = default if value is None else int(value)
    if normalized < 1 or normalized > maximum:
        raise ValueError(f"Limit must be between 1 and {maximum}.")
    return normalized


def _error(tool_name: str, code: str, message: str, *, retryable: bool = False) -> ToolResult:
    from my_digital_brain.ai.models import ToolError

    return ToolResult(
        status="error",
        error=ToolError(
            code=code,
            message=f"{tool_name}: {message}",
            hint="Use only supplied model-facing references and valid structured arguments.",
            retryable=retryable,
        ),
    )
