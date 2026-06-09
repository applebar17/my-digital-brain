from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from my_digital_brain.agentic.contexts import (
    ContradictionJudgeResultContext,
    ContradictionReviewContext,
    EvidenceSpan,
    GraphContextPackage,
    MentionContextItem,
    MentionScanContext,
    PlanningContext,
    SourceContext,
    ToolResultContext,
)
from my_digital_brain.agentic.enums import AgenticStateId, ToolResultStatus
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime_models import AgenticStateInvocation
from my_digital_brain.agentic.runtime import AgenticStateRunner
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ai.protocols import StructuredLLMProvider
from my_digital_brain.ai.schemas import AIRequestContext, StructuredGenerationRequest
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.ingestion.ai_services import _is_graph_alias
from my_digital_brain.ingestion.contracts import (
    ClarificationRequest,
    ExtractionPlan,
    IngestionContextPackage,
    MentionScan,
    SemanticIngestionPlanDraft,
    SourceRecordRef,
)
from my_digital_brain.ingestion.compiler import SemanticExtractionTaskCompiler
from my_digital_brain.ingestion.exceptions import IngestionValidationError


ExecutionContextFactory = Callable[[SourceRecordRef], AgenticToolExecutionContext]


class AgenticIngestionPlanner:
    """Tool-enabled ingestion planner backed by the agentic runtime foundation.

    The planner state may call planning support tools, then this class requests
    a provider-structured `SemanticIngestionPlanDraft`. Backend code compiles
    and validates that plan before the ingestion service continues.
    """

    def __init__(
        self,
        state_runner: AgenticStateRunner,
        *,
        structured_provider: StructuredLLMProvider | None = None,
        execution_context_factory: ExecutionContextFactory | None = None,
        history_service: AgenticHistoryService | None = None,
        compiler: SemanticExtractionTaskCompiler | None = None,
        max_planning_rounds: int = 2,
    ) -> None:
        self.state_runner = state_runner
        self.structured_provider = structured_provider
        self.execution_context_factory = execution_context_factory
        self.history_service = history_service or state_runner.history_service
        self.compiler = compiler or SemanticExtractionTaskCompiler()
        self.max_planning_rounds = max(1, max_planning_rounds)

    @traceable(name="Agentic Ingestion Planning", run_type="chain")
    def plan(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        execution_context = self._execution_context(source)
        planning_context = _planning_context(
            source,
            mention_scan,
            context,
            self.history_service,
        )

        for _ in range(self.max_planning_rounds):
            state_result = self.state_runner.run_state(
                AgenticStateInvocation(
                    state_id=AgenticStateId.MEMORY_INGESTION_PLANNING,
                    context_payload=planning_context,
                    execution_context=execution_context,
                ),
            )
            self.history_service.append_tool_events_to_planning_context(
                planning_context,
                state_result,
                skip_handoff_targets={"contradiction_review"},
            )

            clarification_plan = _clarification_plan_from_state_result(
                state_result,
                source,
                context,
            )
            if clarification_plan is not None:
                return clarification_plan

            if state_result.handoff_target == "contradiction_review":
                contradiction_context = _contradiction_context(
                    state_result.handoff_arguments,
                )
                support_result = self.state_runner.run_state(
                    AgenticStateInvocation(
                        state_id=AgenticStateId.CONTRADICTION_REVIEW,
                        context_payload=contradiction_context,
                        execution_context=execution_context,
                    ),
                )
                if isinstance(contradiction_context, ContradictionReviewContext):
                    contradiction_context = contradiction_context.model_copy(
                        update={
                            "prior_tool_outputs": [
                                *contradiction_context.prior_tool_outputs,
                                *self.history_service.tool_result_contexts_from_events(
                                    support_result.tool_events,
                                ),
                            ],
                        },
                        deep=True,
                    )
                judge_result = self.state_runner.run_structured_state(
                    AgenticStateInvocation(
                        state_id=AgenticStateId.CONTRADICTION_REVIEW,
                        context_payload=contradiction_context,
                        execution_context=execution_context,
                        metadata={
                            "structured_final_output": True,
                            "support_state_status": support_result.status,
                        },
                    ),
                    output_schema=ContradictionJudgeResultContext,
                )
                planning_context.prior_tool_outputs.append(
                    ToolResultContext(
                        tool_name="contradiction_review",
                        status=(
                            ToolResultStatus.FAILED
                            if judge_result.status == "error"
                            else ToolResultStatus.OK
                        ),
                        summary=judge_result.assistant_text
                        or "Contradiction review completed.",
                        data=judge_result.model_dump(mode="json", exclude_none=True),
                    ),
                )
                continue

            plan = self._structured_plan(source, mention_scan, planning_context, context)
            self._validate_plan(plan, source, context)
            return plan

        raise IngestionValidationError(
            "memory_ingestion_planning exceeded the allowed planning rounds "
            "without returning a structured SemanticIngestionPlanDraft."
        )

    @traceable(name="Agentic Ingestion Structured Plan", run_type="parser")
    def _structured_plan(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        planning_context: PlanningContext,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        provider = self.structured_provider or self.state_runner.provider
        if not hasattr(provider, "generate_structured"):
            raise IngestionValidationError(
                "memory_ingestion_planning requires a provider that implements "
                "generate_structured so the final output can be a validated "
                "SemanticIngestionPlanDraft."
            )

        state_config = self.state_runner.state_configs[
            AgenticStateId.MEMORY_INGESTION_PLANNING
        ]
        state_value = str(state_config.state_id)
        model_task = state_config.model_task or state_value
        request_context = AIRequestContext(
            purpose=model_task,
            source_id=source.source_id,
            prompt_id=state_config.prompt_id,
            prompt_version=state_config.prompt_version,
            schema_id=SemanticIngestionPlanDraft.__name__,
            metadata={
                "state_id": state_value,
                "source_type": str(source.source_type),
                "channel": str(source.channel),
            },
        )
        route = self.state_runner.model_router.route(model_task, request_context)
        prompt = self.state_runner.prompt_registry.load(
            state_config.prompt_id,
            state_config.prompt_version,
        ).template
        model_context_payload = self.history_service.model_payload_for_state(
            AgenticStateId.MEMORY_INGESTION_PLANNING,
            planning_context,
        )
        prompt = self.state_runner.system_prompt_with_runtime_context(
            prompt,
            model_context_payload,
        )
        try:
            result = provider.generate_structured(  # type: ignore[attr-defined]
                StructuredGenerationRequest(
                    schema=SemanticIngestionPlanDraft,
                    system_prompt=prompt,
                    input_message={
                        "state_id": state_value,
                        "context": model_context_payload,
                        "final_output_contract": "SemanticIngestionPlanDraft",
                    },
                    model=route.model,
                    temperature=self.state_runner.temperature,
                    max_tokens=self.state_runner.max_tokens,
                    context=request_context,
                    metadata={"route": route.model_dump(mode="json", exclude_none=True)},
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise IngestionValidationError(
                "memory_ingestion_planning returned an invalid structured "
                f"SemanticIngestionPlanDraft: {exc}"
            ) from exc
        draft = SemanticIngestionPlanDraft.model_validate(result.parsed)
        return self.compiler.compile(draft, source, mention_scan, context)

    def _execution_context(self, source: SourceRecordRef) -> AgenticToolExecutionContext:
        if self.execution_context_factory is not None:
            context = self.execution_context_factory(source)
        else:
            context = AgenticToolExecutionContext()
        context.current_text = source.raw_text
        context.metadata = {
            **context.metadata,
            "source_id": source.source_id,
            "source_type": str(source.source_type),
            "channel": str(source.channel),
        }
        return context

    def _validate_plan(
        self,
        plan: ExtractionPlan,
        source: SourceRecordRef,
        context: IngestionContextPackage,
    ) -> None:
        known_aliases = set(context.aliases)
        unknown_aliases: list[str] = []
        for task in plan.tasks:
            refs = [task.target_ref, *task.required_context_refs]
            for ref in refs:
                if ref and _is_graph_alias(ref) and ref not in known_aliases:
                    unknown_aliases.append(ref)
        if plan.clarification is not None:
            for ref in plan.clarification.target_refs:
                if _is_graph_alias(ref) and ref not in known_aliases:
                    unknown_aliases.append(ref)
        if unknown_aliases:
            raise IngestionValidationError(
                "Extraction plan referenced graph aliases that were not present "
                f"in compact context: {sorted(set(unknown_aliases))}."
            )


def _planning_context(
    source: SourceRecordRef,
    mention_scan: MentionScan,
    context: IngestionContextPackage,
    history_service: AgenticHistoryService,
) -> PlanningContext:
    text = source.raw_text or source.content_ref or ""
    source_alias = "SOURCE_000001"
    return PlanningContext(
        source=SourceContext(
            source_id=source_alias,
            normalized_text=source.raw_text,
            transcript_text=source.raw_text if str(source.source_type) == "transcript" else None,
            media_refs=[source.content_ref] if source.content_ref else [],
            evidence=[
                EvidenceSpan(
                    text=mention.evidence_text or mention.text,
                    span_start=mention.span_start,
                    span_end=mention.span_end,
                    source_ref=source_alias,
                )
                for mention in mention_scan.mentions
                if mention.evidence_text or mention.text
            ],
            metadata={"source_type": str(source.source_type), "channel": str(source.channel)},
        ),
        conversation=history_service.source_conversation_context(
            source_text=text or "Memory source",
            timezone=str(source.metadata.get("timezone") or "UTC"),
        ),
        mention_scan=MentionScanContext(
            source_id=source_alias,
            mentions=[
                MentionContextItem(
                    kind=str(mention.kind),
                    text=mention.text,
                    evidence_text=mention.evidence_text,
                    span_start=mention.span_start,
                    span_end=mention.span_end,
                    hints={
                        key: value
                        for key, value in {
                            "possible_normalized_value": mention.possible_normalized_value,
                            "ambiguity_hint": mention.ambiguity_hint,
                        }.items()
                        if value
                    },
                )
                for mention in mention_scan.mentions
            ],
        ),
        graph_context=GraphContextPackage(
            package_id=context.context_package_id,
            aliases={alias: alias for alias in context.aliases},
            candidate_matches=list(context.entities),
            relationship_contexts=list(context.relationships),
            known_ambiguities=list(context.notes),
            metadata={"source_alias": source_alias},
        ),
        timezone=str(source.metadata.get("timezone") or "UTC"),
        metadata={"context_package_id": context.context_package_id},
    )

def _contradiction_context(arguments: dict[str, Any]):
    from my_digital_brain.agentic.contexts import ContradictionReviewContext

    return ContradictionReviewContext(
        proposed_write_ref=arguments.get("proposed_write_ref"),
        proposed_write=dict(arguments.get("proposed_write") or {}),
        affected_entity_refs=list(arguments.get("affected_entity_refs") or []),
        affected_relationship_refs=list(arguments.get("affected_relationship_refs") or []),
        source_refs=list(arguments.get("source_refs") or []),
        agent_doubt=arguments.get("agent_doubt") or "The planner requested review.",
        metadata=dict(arguments.get("metadata") or {}),
    )


def _clarification_plan_from_state_result(
    state_result,
    source: SourceRecordRef,
    context: IngestionContextPackage,
) -> ExtractionPlan | None:
    for event in state_result.tool_events:
        data = event.data or {}
        if data.get("operation") != "request_user_clarification":
            continue
        packet = data.get("clarification_packet")
        if not isinstance(packet, dict):
            continue
        questions = packet.get("questions")
        if not isinstance(questions, list) or not questions:
            continue
        first_question = questions[0]
        option_labels = [
            str(option.get("label"))
            for option in first_question.get("options", [])
            if isinstance(option, dict) and option.get("label")
        ]
        options = "; ".join(option_labels) if option_labels else None
        return ExtractionPlan(
            source_id=source.source_id,
            context_package_id=context.context_package_id,
            execution_mode="needs_clarification_first",
            reason=str(packet.get("reason") or "Clarification required before extraction."),
            clarification=ClarificationRequest(
                doubt=str(first_question.get("question") or "Clarification is needed."),
                reason=str(packet.get("reason") or "Clarification required before extraction."),
                target_refs=list(packet.get("target_refs") or []),
                options=options,
                blocking=True,
                metadata={"clarification_packet": packet},
            ),
        )
    return None
