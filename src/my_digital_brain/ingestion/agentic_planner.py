from __future__ import annotations

from collections.abc import Callable
from typing import Any

from my_digital_brain.agentic.contexts import (
    ConversationContext,
    EvidenceSpan,
    GraphContextPackage,
    MentionContextItem,
    MentionScanContext,
    PlanningContext,
    SourceContext,
    ToolResultContext,
)
from my_digital_brain.agentic.enums import AgenticStateId, ToolResultStatus
from my_digital_brain.agentic.messages import NeutralConversationMessage
from my_digital_brain.agentic.runtime_models import AgenticStateInvocation, AgenticStateRunResult
from my_digital_brain.agentic.runtime import AgenticStateRunner
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ingestion.ai_services import _is_graph_alias
from my_digital_brain.ingestion.contracts import (
    ExtractionPlan,
    IngestionContextPackage,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.exceptions import IngestionValidationError


ExecutionContextFactory = Callable[[SourceRecordRef], AgenticToolExecutionContext]


class AgenticIngestionPlanner:
    """Tool-enabled ingestion planner backed by the agentic runtime foundation.

    The planner state must call `submit_extraction_plan`. The submitted plan is
    still validated by backend code before this class returns it to the
    ingestion service.
    """

    def __init__(
        self,
        state_runner: AgenticStateRunner,
        *,
        execution_context_factory: ExecutionContextFactory | None = None,
        max_planning_rounds: int = 2,
    ) -> None:
        self.state_runner = state_runner
        self.execution_context_factory = execution_context_factory
        self.max_planning_rounds = max(1, max_planning_rounds)

    def plan(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        execution_context = self._execution_context(source)
        planning_context = _planning_context(source, mention_scan, context)

        for _ in range(self.max_planning_rounds):
            state_result = self.state_runner.run_state(
                AgenticStateInvocation(
                    state_id=AgenticStateId.MEMORY_INGESTION_PLANNING,
                    context_payload=planning_context,
                    execution_context=execution_context,
                ),
            )
            submitted = _submitted_plan(state_result)
            if submitted is not None:
                self._validate_plan(submitted, source, context)
                return submitted
            submission_error = _submitted_plan_error(state_result)
            if submission_error is not None:
                raise IngestionValidationError(
                    "memory_ingestion_planning submitted an invalid "
                    f"ExtractionPlan: {submission_error}"
                )

            if state_result.handoff_target == "contradiction_review":
                judge_result = self.state_runner.run_state(
                    AgenticStateInvocation(
                        state_id=AgenticStateId.CONTRADICTION_REVIEW,
                        context_payload=_contradiction_context(
                            state_result.handoff_arguments,
                        ),
                        execution_context=execution_context,
                    ),
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

            raise IngestionValidationError(
                "memory_ingestion_planning completed without calling "
                "submit_extraction_plan."
            )

        raise IngestionValidationError(
            "memory_ingestion_planning exceeded the allowed planning rounds "
            "without submitting an ExtractionPlan."
        )

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
        if plan.source_id != source.source_id:
            raise IngestionValidationError(
                f"Extraction plan returned source_id '{plan.source_id}' "
                f"but expected '{source.source_id}'."
            )
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
) -> PlanningContext:
    text = source.raw_text or source.content_ref or ""
    return PlanningContext(
        source=SourceContext(
            source_id=source.source_id,
            normalized_text=source.raw_text,
            transcript_text=source.raw_text if str(source.source_type) == "transcript" else None,
            media_refs=[source.content_ref] if source.content_ref else [],
            evidence=[
                EvidenceSpan(
                    text=mention.evidence_text or mention.text,
                    span_start=mention.span_start,
                    span_end=mention.span_end,
                    source_ref=source.source_id,
                )
                for mention in mention_scan.mentions
                if mention.evidence_text or mention.text
            ],
            metadata={"source_type": str(source.source_type), "channel": str(source.channel)},
        ),
        conversation=ConversationContext(
            current_message=NeutralConversationMessage.user(text or "Memory source"),
        ),
        mention_scan=MentionScanContext(
            source_id=source.source_id,
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
            aliases=dict(context.aliases),
            candidate_matches=list(context.entities),
            relationship_contexts=list(context.relationships),
            known_ambiguities=list(context.notes),
            metadata=dict(context.metadata),
        ),
        timezone=str(source.metadata.get("timezone") or "UTC"),
        metadata={"context_package_id": context.context_package_id},
    )


def _submitted_plan(state_result: AgenticStateRunResult) -> ExtractionPlan | None:
    for event in reversed(state_result.tool_events):
        data = event.data or {}
        if data.get("operation") != "submit_extraction_plan":
            continue
        payload = data.get("extraction_plan")
        if isinstance(payload, dict):
            return ExtractionPlan.model_validate(payload)
    return None


def _submitted_plan_error(state_result: AgenticStateRunResult) -> str | None:
    for event in reversed(state_result.tool_events):
        if event.tool_name != "submit_extraction_plan" or event.status == "ok":
            continue
        error = event.error or {}
        message = error.get("message")
        hint = error.get("hint")
        if message and hint:
            return f"{message} Hint: {hint}"
        if message:
            return str(message)
        return "submit_extraction_plan failed without a tool error message."
    return None


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
