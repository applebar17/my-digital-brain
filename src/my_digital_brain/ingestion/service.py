from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import logging

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.contracts import (
    CandidateClaim,
    CandidateEntity,
    CandidateMetadataPatch,
    CandidateOutput,
    CandidatePerception,
    CandidateRelationship,
    CandidateRelationshipContext,
    ExtractionTask,
    IngestionContextPackage,
    IngestionResult,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import (
    ExtractionExecutionMode,
    ExtractionTaskType,
    IngestionStatus,
)
from my_digital_brain.ingestion.ontology import (
    REF_PRODUCING_TASK_TYPES,
    ontology_prompt_payload,
)
from my_digital_brain.ingestion.protocols import (
    CandidateGraphAssembler,
    FocusedExtractor,
    GraphWritePlanBuilder,
    GraphWritePlanExecutor,
    GraphVectorizationService,
    IngestionContextRetriever,
    IngestionPlanner,
    IngestionProcessStore,
    MentionScanner,
    ResolutionService,
)
from my_digital_brain.ingestion.validation import IngestionValidator


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionService:
    """Transport-neutral ingestion orchestrator.

    The service coordinates pluggable scanner, context, planner, and extractor
    components. Graph writes only happen when write-plan components are injected.
    """

    scanner: MentionScanner
    context_retriever: IngestionContextRetriever
    planner: IngestionPlanner
    extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    assembler: CandidateGraphAssembler = field(default_factory=CandidateMemoryGraphAssembler)
    validator: IngestionValidator = field(default_factory=IngestionValidator)
    resolution_service: ResolutionService | None = None
    write_plan_builder: GraphWritePlanBuilder | None = None
    write_plan_executor: GraphWritePlanExecutor | None = None
    vectorization_service: GraphVectorizationService | None = None
    execute_write_plan: bool = False
    process_store: IngestionProcessStore | None = None

    @traceable(name="Ingestion Process Source", run_type="chain")
    def process_source(self, source: SourceRecordRef) -> IngestionResult:
        log_event(
            logger,
            "ingestion.source.start",
            component="ingestion",
            source_id=source.source_id,
            source_type=str(source.source_type),
            channel=str(source.channel),
            execute_write_plan=self.execute_write_plan,
            extractor_count=len(self.extractors),
        )
        if self.process_store is not None:
            self.process_store.save_source(source)

        mention_scan = self.scanner.scan(source)
        log_event(
            logger,
            "ingestion.mention_scan.done",
            component="ingestion",
            source_id=source.source_id,
            mention_count=len(mention_scan.mentions),
            mention_kinds=[str(mention.kind) for mention in mention_scan.mentions],
        )
        context = self.context_retriever.retrieve(source, mention_scan)
        log_event(
            logger,
            "ingestion.context.done",
            component="ingestion",
            source_id=source.source_id,
            context_package_id=context.context_package_id,
            context_entity_count=len(context.entities),
            context_relationship_count=len(context.relationships),
            context_note_count=len(context.notes),
        )
        extraction_plan = self.planner.plan(source, mention_scan, context)
        log_event(
            logger,
            "ingestion.plan.done",
            component="ingestion",
            source_id=source.source_id,
            extraction_plan_id=extraction_plan.extraction_plan_id,
            execution_mode=str(extraction_plan.execution_mode),
            task_count=len(extraction_plan.tasks),
            task_types=[str(task.task_type) for task in extraction_plan.tasks],
            has_clarification=extraction_plan.clarification is not None,
            context_gap_count=len(extraction_plan.context_gaps),
        )

        if (
            extraction_plan.execution_mode
            == ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST
            and extraction_plan.clarification is not None
        ):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    clarification=extraction_plan.clarification,
                ),
            )

        if extraction_plan.execution_mode == ExtractionExecutionMode.NEEDS_CONTEXT_EXPANSION:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.PLANNED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    metadata={"reason": "context expansion requested by planner"},
                ),
            )

        if not extraction_plan.tasks:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="extraction_plan.tasks",
                            message=(
                                "The ingestion planner produced no extraction tasks. "
                                "A memory cannot be stored until at least one focused "
                                "task, clarification, or context-expansion request is "
                                "produced."
                            ),
                            code="empty_extraction_plan",
                            details={
                                "execution_mode": str(extraction_plan.execution_mode),
                            },
                        )
                    ],
                ),
            )

        candidates: list[CandidateOutput] = []
        missing_extractor_issues: list[ValidationIssue] = []
        ref_validation_issues: list[ValidationIssue] = []
        candidate_ref_catalog: dict[str, dict[str, object]] = {}
        previous_action_summaries: list[dict[str, object]] = []
        execution_tasks = _ordered_tasks_for_execution(extraction_plan.tasks)
        for task_index, task in enumerate(execution_tasks):
            task_context = _context_for_task(
                context,
                task,
                candidate_ref_catalog,
                previous_action_summaries,
            )
            task = _task_for_execution(
                task,
                task_context,
                candidate_ref_catalog,
                previous_action_summaries,
            )
            extractor = self._find_extractor(task)
            if extractor is None:
                missing_extractor_issues.append(
                    ValidationIssue(
                        field_path=f"extraction_plan.tasks[{task_index}]",
                        message=(
                            f"No focused extractor is registered for task type "
                            f"'{task.task_type}'. Register a backend extractor or "
                            "adjust the planner to avoid this task."
                        ),
                        code="missing_focused_extractor",
                        details={"task_id": task.task_id, "task_type": str(task.task_type)},
                    ),
                )
                continue
            task_candidates = list(extractor.extract(source, task, task_context))
            task_ref_issues = _validate_extracted_refs(
                task_candidates,
                candidate_ref_catalog,
                task_context.aliases,
                task,
            )
            if task_ref_issues:
                ref_validation_issues.extend(task_ref_issues)
                continue
            candidates.extend(task_candidates)
            _update_candidate_ref_catalog(candidate_ref_catalog, task_candidates, task)
            previous_action_summaries.append(
                _task_execution_summary(task, task_candidates),
            )

        log_event(
            logger,
            "ingestion.extraction.done",
            component="ingestion",
            source_id=source.source_id,
            extraction_plan_id=extraction_plan.extraction_plan_id,
            candidate_count=len(candidates),
            missing_extractor_count=len(missing_extractor_issues),
            ref_validation_error_count=len(ref_validation_issues),
        )

        if missing_extractor_issues or ref_validation_issues:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    validation_errors=[
                        *missing_extractor_issues,
                        *ref_validation_issues,
                    ],
                ),
            )

        candidate_graph = self.assembler.assemble(source, extraction_plan, candidates)
        if not _candidate_graph_has_outputs(candidate_graph):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    validation_errors=[
                        ValidationIssue(
                            field_path="candidate_graph",
                            message=(
                                "Focused extraction produced no memory candidates. "
                                "No graph write can be executed from an empty candidate "
                                "graph."
                            ),
                            code="empty_candidate_graph",
                            details={
                                "task_count": len(extraction_plan.tasks),
                            },
                        )
                    ],
                ),
            )

        validation_result = self.validator.validate_candidate_graph(candidate_graph)
        if not validation_result.is_valid:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    validation_errors=validation_result.issues,
                ),
            )

        if self.resolution_service is None or self.write_plan_builder is None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.CANDIDATE_READY,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                ),
            )

        resolution = self.resolution_service.resolve(candidate_graph, context)
        if resolution.clarification is not None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    clarification=resolution.clarification,
                ),
            )

        write_plan = self.write_plan_builder.build(candidate_graph, resolution, context)
        write_counts = _write_plan_counts(write_plan)
        log_event(
            logger,
            "ingestion.write_plan.done",
            component="ingestion",
            source_id=source.source_id,
            write_plan_id=write_plan.write_plan_id,
            mutation_count=sum(write_counts.values()),
            write_counts=write_counts,
            resolution_decision_count=len(write_plan.resolution_decisions),
        )
        if not _write_plan_has_mutations(write_plan):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    write_plan=write_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="write_plan",
                            message=(
                                "The resolved write plan contains no graph mutations. "
                                "Memory storage is not considered successful unless at "
                                "least one node, relationship, or patch is written."
                            ),
                            code="empty_write_plan",
                            details={
                                "candidate_count": _candidate_graph_output_count(
                                    candidate_graph,
                                ),
                            },
                        )
                    ],
                ),
            )

        write_validation = self.validator.validate_write_plan(write_plan)
        if not write_validation.is_valid:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    write_plan=write_plan,
                    validation_errors=write_validation.issues,
                ),
            )

        if self.write_plan_executor is not None and self.execute_write_plan:
            result = self.write_plan_executor.execute(write_plan)
            result.mention_scan = mention_scan
            result.extraction_plan = extraction_plan
            result.candidate_graph = candidate_graph
            if result.status == IngestionStatus.WRITTEN:
                self._vectorize_written_result(result)
            return self._finish(result)

        return self._finish(
            IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.WRITE_PLAN_READY,
                mention_scan=mention_scan,
                extraction_plan=extraction_plan,
                candidate_graph=candidate_graph,
                write_plan=write_plan,
            ),
        )

    def _find_extractor(self, task) -> FocusedExtractor | None:
        for extractor in self.extractors:
            if extractor.supports(task):
                return extractor
        return None

    def _finish(self, result: IngestionResult) -> IngestionResult:
        if result.validation_errors:
            log_event(
                logger,
                "ingestion.validation_failed",
                level="warning",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                status=str(result.status),
                validation_error_count=len(result.validation_errors),
                validation_errors=_validation_issue_summaries(result.validation_errors),
            )
        log_event(
            logger,
            "ingestion.result",
            component="ingestion",
            source_id=result.source_id,
            ingestion_id=result.ingestion_id,
            status=str(result.status),
            validation_error_count=len(result.validation_errors),
            validation_error_codes=[
                issue.code for issue in result.validation_errors if issue.code
            ],
            has_clarification=result.clarification is not None,
            write_counts=_write_plan_counts(result.write_plan) if result.write_plan else None,
        )
        if self.process_store is not None:
            self.process_store.record_result(result)
        return result

    @traceable(name="Ingestion Vectorize Written Result", run_type="chain")
    def _vectorize_written_result(self, result: IngestionResult) -> None:
        if self.vectorization_service is None:
            return
        try:
            vectorization = self.vectorization_service.vectorize_ingestion_result(result)
            if hasattr(vectorization, "model_dump"):
                payload = vectorization.model_dump(mode="json", exclude_none=True)
            elif isinstance(vectorization, dict):
                payload = dict(vectorization)
            else:
                payload = {"result": str(vectorization)}
            result.metadata = {**result.metadata, "vectorization": payload}
            log_event(
                logger,
                "ingestion.vectorization.done",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                vectorization=payload,
            )
        except Exception as exc:  # pragma: no cover - defensive safety for external vector stores
            result.metadata = {
                **result.metadata,
                "vectorization": {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            }
            log_event(
                logger,
                "ingestion.vectorization.failed",
                level="error",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )


def _candidate_graph_has_outputs(candidate_graph) -> bool:
    return _candidate_graph_output_count(candidate_graph) > 0


def _candidate_graph_output_count(candidate_graph) -> int:
    return sum(
        len(items)
        for items in (
            candidate_graph.candidate_entities,
            candidate_graph.candidate_relationships,
            candidate_graph.candidate_claims,
            candidate_graph.candidate_perceptions,
            candidate_graph.candidate_relationship_contexts,
            candidate_graph.candidate_metadata_patches,
        )
    )


def _write_plan_has_mutations(write_plan) -> bool:
    return any(
        (
            write_plan.nodes_to_create,
            write_plan.nodes_to_update,
            write_plan.relationships_to_create,
            write_plan.relationships_to_update,
            write_plan.claims_to_create,
            write_plan.perceptions_to_create,
            write_plan.relationship_contexts_to_create,
            write_plan.metadata_patches,
        )
    )


def _write_plan_counts(write_plan) -> dict[str, int]:
    return {
        "nodes_to_create": len(write_plan.nodes_to_create),
        "nodes_to_update": len(write_plan.nodes_to_update),
        "relationships_to_create": len(write_plan.relationships_to_create),
        "relationships_to_update": len(write_plan.relationships_to_update),
        "claims_to_create": len(write_plan.claims_to_create),
        "perceptions_to_create": len(write_plan.perceptions_to_create),
        "relationship_contexts_to_create": len(write_plan.relationship_contexts_to_create),
        "metadata_patches": len(write_plan.metadata_patches),
    }


def _ordered_tasks_for_execution(
    tasks: Sequence[ExtractionTask],
) -> list[ExtractionTask]:
    return sorted(
        tasks,
        key=lambda task: (
            0 if _task_type(task) in REF_PRODUCING_TASK_TYPES else 1,
            int(task.metadata.get("semantic_action_index") or 0),
            str(_task_type(task)),
            task.task_id,
        ),
    )


def _context_for_task(
    context: IngestionContextPackage,
    task: ExtractionTask,
    candidate_ref_catalog: dict[str, dict[str, object]],
    previous_action_summaries: Sequence[dict[str, object]],
) -> IngestionContextPackage:
    return context.model_copy(
        update={
            "metadata": {
                **context.metadata,
                "ingestion_ontology": ontology_prompt_payload(),
                "candidate_ref_catalog": list(candidate_ref_catalog.values()),
                "previous_action_summaries": list(previous_action_summaries[-6:]),
                "current_action": _current_action_payload(task),
            },
        },
        deep=True,
    )


def _task_for_execution(
    task: ExtractionTask,
    context: IngestionContextPackage,
    candidate_ref_catalog: dict[str, dict[str, object]],
    previous_action_summaries: Sequence[dict[str, object]],
) -> ExtractionTask:
    return task.model_copy(
        update={
            "metadata": {
                **task.metadata,
                "candidate_ref_catalog": list(candidate_ref_catalog.values()),
                "previous_action_summaries": list(previous_action_summaries[-6:]),
                "allowed_graph_aliases": sorted(context.aliases),
                "ontology": ontology_prompt_payload(),
            },
        },
        deep=True,
    )


def _current_action_payload(task: ExtractionTask) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            "task_id": task.task_id,
            "task_type": str(_task_type(task)),
            "semantic_action_ref": task.metadata.get("semantic_action_ref"),
            "semantic_action_kind": task.metadata.get("semantic_action_kind"),
            "semantic_action_goal": task.metadata.get("semantic_action_goal"),
            "semantic_action_index": task.metadata.get("semantic_action_index"),
            "ref_policy": task.metadata.get("ref_policy"),
            "suggested_candidate_refs": task.metadata.get("suggested_candidate_refs"),
        }.items()
        if value not in (None, "", [], {})
    }


def _validate_extracted_refs(
    candidates: Sequence[CandidateOutput],
    candidate_ref_catalog: dict[str, dict[str, object]],
    aliases: dict[str, str],
    task: ExtractionTask,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    known_candidate_refs = set(candidate_ref_catalog)
    known_aliases = set(aliases)
    for candidate_index, candidate in enumerate(candidates):
        for field_name, refs in _candidate_external_refs(candidate):
            for ref_index, ref in enumerate(refs):
                if not ref:
                    continue
                if ref.startswith("CANDIDATE_"):
                    if ref not in known_candidate_refs:
                        issues.append(
                            ValidationIssue(
                                field_path=(
                                    f"task[{task.task_id}].candidates[{candidate_index}]"
                                    f".{field_name}[{ref_index}]"
                                ),
                                message=(
                                    f"Unknown candidate ref '{ref}'. Ref-consuming "
                                    "extractors may only use candidate refs produced by "
                                    "earlier extraction actions."
                                ),
                                code="unknown_extraction_candidate_ref",
                                details={
                                    "ref": ref,
                                    "task_id": task.task_id,
                                    "task_type": str(_task_type(task)),
                                },
                            ),
                        )
                    continue
                if _looks_like_graph_alias(ref):
                    if ref not in known_aliases:
                        issues.append(
                            ValidationIssue(
                                field_path=(
                                    f"task[{task.task_id}].candidates[{candidate_index}]"
                                    f".{field_name}[{ref_index}]"
                                ),
                                message=(
                                    f"Unknown graph alias '{ref}'. Extractors may only "
                                    "use aliases supplied in compact graph context."
                                ),
                                code="unknown_extraction_graph_alias_ref",
                                details={
                                    "ref": ref,
                                    "task_id": task.task_id,
                                    "task_type": str(_task_type(task)),
                                },
                            ),
                        )
                    continue
                issues.append(
                    ValidationIssue(
                        field_path=(
                            f"task[{task.task_id}].candidates[{candidate_index}]"
                            f".{field_name}[{ref_index}]"
                        ),
                        message=(
                            f"Unsupported reference '{ref}'. Use a provided graph alias "
                            "or a candidate ref from an earlier extraction action."
                        ),
                        code="unsupported_extraction_ref",
                        details={
                            "ref": ref,
                            "task_id": task.task_id,
                            "task_type": str(_task_type(task)),
                        },
                    ),
                )
    return issues


def _candidate_external_refs(
    candidate: CandidateOutput,
) -> list[tuple[str, list[str]]]:
    if isinstance(candidate, CandidateRelationship):
        return [("from_ref", [candidate.from_ref]), ("to_ref", [candidate.to_ref])]
    if isinstance(candidate, CandidateClaim):
        return [
            ("about_refs", list(candidate.about_refs)),
            ("contradiction_refs", list(candidate.contradiction_refs)),
        ]
    if isinstance(candidate, CandidatePerception):
        return [("target_ref", [candidate.target_ref])]
    if isinstance(candidate, CandidateRelationshipContext):
        return [("from_ref", [candidate.from_ref]), ("to_ref", [candidate.to_ref])]
    if isinstance(candidate, CandidateMetadataPatch):
        return [("target_ref", [candidate.target_ref])]
    return []


def _update_candidate_ref_catalog(
    candidate_ref_catalog: dict[str, dict[str, object]],
    candidates: Sequence[CandidateOutput],
    task: ExtractionTask,
) -> None:
    for candidate in candidates:
        candidate_ref_catalog[candidate.local_ref] = {
            key: value
            for key, value in {
                "local_ref": candidate.local_ref,
                "candidate_kind": type(candidate).__name__,
                "task_type": str(_task_type(task)),
                "semantic_action_ref": task.metadata.get("semantic_action_ref"),
                "summary": _candidate_summary(candidate),
            }.items()
            if value not in (None, "", [], {})
        }


def _task_execution_summary(
    task: ExtractionTask,
    candidates: Sequence[CandidateOutput],
) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "task_type": str(_task_type(task)),
        "semantic_action_ref": task.metadata.get("semantic_action_ref"),
        "semantic_action_goal": task.metadata.get("semantic_action_goal"),
        "candidate_count": len(candidates),
        "candidate_refs": [candidate.local_ref for candidate in candidates],
        "candidate_summaries": [_candidate_summary(candidate) for candidate in candidates[:5]],
    }


def _candidate_summary(candidate: CandidateOutput) -> str:
    if isinstance(candidate, CandidateEntity):
        return _short_text(
            candidate.display_name
            or candidate.description
            or f"{candidate.entity_type} candidate",
            max_chars=120,
        )
    if isinstance(candidate, CandidateRelationship):
        detail = candidate.relationship_detail or candidate.relationship_kind
        suffix = f" ({detail})" if detail else ""
        return _short_text(
            f"{candidate.from_ref} -{candidate.relationship_type}{suffix}-> {candidate.to_ref}",
            max_chars=120,
        )
    if isinstance(candidate, CandidateClaim):
        return _short_text(candidate.text, max_chars=120)
    if isinstance(candidate, CandidatePerception):
        return _short_text(candidate.description, max_chars=120)
    if isinstance(candidate, CandidateRelationshipContext):
        return _short_text(
            candidate.description
            or f"Relationship context {candidate.from_ref} / {candidate.to_ref}",
            max_chars=120,
        )
    if isinstance(candidate, CandidateMetadataPatch):
        return _short_text(candidate.reason or candidate.path, max_chars=120)
    return candidate.local_ref


def _looks_like_graph_alias(ref: str) -> bool:
    prefixes = ("NODE_", "REL_", "CLAIM_", "SOURCE_", "RELCTX_")
    return ref.startswith(prefixes)


def _task_type(task: ExtractionTask) -> ExtractionTaskType:
    return ExtractionTaskType(task.task_type)


def _validation_issue_summaries(
    issues: Sequence[ValidationIssue],
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for issue in issues[:limit]:
        summaries.append(
            {
                key: value
                for key, value in {
                    "code": issue.code,
                    "field_path": issue.field_path,
                    "message": _short_text(issue.message),
                    "details": _compact_issue_details(issue.details),
                }.items()
                if value not in (None, "", {}, [])
            },
        )
    if len(issues) > limit:
        summaries.append({"code": "truncated", "remaining_count": len(issues) - limit})
    return summaries


def _compact_issue_details(details: dict[str, object]) -> dict[str, object]:
    allowed_keys = {
        "label",
        "relationship_type",
        "ref",
        "count",
        "execution_mode",
        "task_id",
        "task_type",
        "candidate_count",
    }
    return {
        key: _short_text(value) if isinstance(value, str) else value
        for key, value in details.items()
        if key in allowed_keys
    }


def _short_text(value: str, *, max_chars: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}..."
