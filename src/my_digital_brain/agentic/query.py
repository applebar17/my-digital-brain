from __future__ import annotations

from typing import Any, Protocol

from my_digital_brain.agentic.base import AgenticModel
from my_digital_brain.agentic.contexts import (
    AnswerContext,
    QueryRetrievalPlan,
    QueryRetrievalPlanningContext,
    QueryRetrievalResultContext,
    ToolResultContext,
)
from my_digital_brain.agentic.enums import ToolResultStatus


class GraphQueryProvider(Protocol):
    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[Any]: ...

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> Any: ...


class MemoryQueryFoundationResult(AgenticModel):
    retrieval_plan: QueryRetrievalPlan
    retrieval_result: QueryRetrievalResultContext
    answer_context: AnswerContext | None = None
    tool_result: ToolResultContext


class MemoryQueryFoundationService:
    """Deterministic query foundation using existing graph read helpers.

    This does not perform semantic retrieval, autonomous multi-tool loops, or
    provider-backed answer generation. It prepares explicit context objects that
    later agentic states and answer-generation providers can consume.
    """

    def __init__(self, graph: GraphQueryProvider | None = None) -> None:
        self.graph = graph

    def build_retrieval_plan(
        self,
        context: QueryRetrievalPlanningContext,
        *,
        seed_id: str | None = None,
        view_type: str = "context_package",
    ) -> QueryRetrievalPlan:
        return QueryRetrievalPlan(
            question=context.question,
            seed_id=seed_id,
            query_text=context.question if seed_id is None else None,
            view_type=view_type,
            evidence_requirements=[
                "Use source evidence when available.",
                "Preserve affective context and original user wording when relevant.",
                "State uncertainty when graph context is weak or missing.",
            ],
            metadata={"desired_view": context.desired_view or view_type},
        )

    def retrieve(self, plan: QueryRetrievalPlan) -> QueryRetrievalResultContext:
        if self.graph is None:
            return QueryRetrievalResultContext(
                question=plan.question,
                plan=plan,
                no_memory_reason="No graph query provider is configured.",
                uncertainty_notes=["Graph context retrieval is not wired yet."],
            )

        seed_id = plan.seed_id or self._resolve_seed_id(plan.query_text or plan.question)
        if seed_id is None:
            return QueryRetrievalResultContext(
                question=plan.question,
                plan=plan,
                no_memory_reason="No matching graph seed was found.",
                uncertainty_notes=[
                    "The memory graph did not provide a clear entity, place, event, or topic match."
                ],
            )

        package = self.graph.get_context_package(
            seed_id,
            include_history=plan.include_history,
            timeline_limit=plan.timeline_limit,
            relationship_limit=plan.relationship_limit,
        )
        package_payload = _model_or_mapping_to_dict(package)
        return QueryRetrievalResultContext(
            question=plan.question,
            plan=plan,
            seed_id=seed_id,
            seed_title=_target_title(package_payload.get("target", {})),
            context_package=package_payload,
            evidence=list(package_payload.get("evidence") or []),
            uncertainty_notes=list(package_payload.get("notes") or []),
        )

    def build_answer_context(self, result: QueryRetrievalResultContext) -> AnswerContext | None:
        if result.context_package is None:
            return None
        return AnswerContext(
            question=result.question,
            context_package=result.context_package,
            evidence_rules=[
                "Use only the provided memory graph context.",
                "Do not expose raw UUIDs when aliases are available.",
                "Mention uncertainty when evidence is weak or absent.",
                "Preserve emotional and perceptual context when relevant.",
            ],
            answer_style_hints=[
                "Natural and concise.",
                "Human-friendly, not diagnostic.",
            ],
            uncertainty_notes=result.uncertainty_notes,
            metadata={"seed_id": result.seed_id or ""},
        )

    def run(
        self,
        context: QueryRetrievalPlanningContext,
        *,
        seed_id: str | None = None,
    ) -> MemoryQueryFoundationResult:
        plan = self.build_retrieval_plan(context, seed_id=seed_id)
        retrieval = self.retrieve(plan)
        answer = self.build_answer_context(retrieval)
        tool_result = self._tool_result(retrieval, answer)
        return MemoryQueryFoundationResult(
            retrieval_plan=plan,
            retrieval_result=retrieval,
            answer_context=answer,
            tool_result=tool_result,
        )

    def _resolve_seed_id(self, query: str) -> str | None:
        if self.graph is None:
            return None
        results = self.graph.search_nodes(query=query, limit=5)
        if not results:
            return None
        first = results[0]
        properties = getattr(first, "properties", None)
        if isinstance(properties, dict) and properties.get("id"):
            return str(properties["id"])
        if isinstance(first, dict):
            properties = first.get("properties")
            if isinstance(properties, dict) and properties.get("id"):
                return str(properties["id"])
            if first.get("id"):
                return str(first["id"])
        return None

    def _tool_result(
        self,
        retrieval: QueryRetrievalResultContext,
        answer: AnswerContext | None,
    ) -> ToolResultContext:
        if answer is None:
            return ToolResultContext(
                tool_name="query_memory_context",
                status=ToolResultStatus.FAILED,
                summary=retrieval.no_memory_reason or "No memory context was found.",
                unresolved_questions=[retrieval.question],
                recommended_next_action="Ask the user for a more specific memory target.",
                data=retrieval.model_dump(mode="json", exclude_none=True),
            )
        title = retrieval.seed_title or retrieval.seed_id or "matching memory"
        return ToolResultContext(
            tool_name="query_memory_context",
            status=ToolResultStatus.OK,
            summary=f"Retrieved graph context for {title}.",
            important_refs=[retrieval.seed_id] if retrieval.seed_id else [],
            recommended_next_action="Generate a grounded answer from AnswerContext.",
            data={
                "answer_context": answer.model_dump(mode="json", exclude_none=True),
                "retrieval_result": retrieval.model_dump(mode="json", exclude_none=True),
            },
        )


def _model_or_mapping_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Unsupported graph context package type: {type(value).__name__}")


def _target_title(target: dict[str, Any]) -> str | None:
    for key in ("title", "display_name", "name", "label", "id"):
        value = target.get(key)
        if value:
            return str(value)
    return None
