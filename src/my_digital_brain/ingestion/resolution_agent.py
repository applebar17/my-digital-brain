"""LLM proposal boundary for context-driven identity resolution."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.protocols import LLMProvider, ModelRouter
from my_digital_brain.ai.schemas import AIRequestContext, ChatMessage
from my_digital_brain.ai.session import (
    LLMSessionAwaitingTool,
    LLMSessionCompleted,
    LLMSessionContinuation,
    LLMSessionRequest,
    continuation_with_tool_result,
)
from my_digital_brain.clarification.contracts import ClarificationHandoffRequest
from my_digital_brain.core.owner_context import owner_prompt_block
from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    EntityLookupContextPacket,
    IngestionContextPackage,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
    ResolvedEntityMap,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.resolution_context import (
    build_other_planned_context_packet,
)
from my_digital_brain.ingestion.resolution_proposals import (
    ResolutionProposalCompiler,
    ResolutionProposalValidationError,
    ResolutionProposalValidator,
)
from my_digital_brain.ingestion.resolution_toolboxes import build_resolution_toolbox

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ResolutionProposalRun:
    actions: list[ResolutionToolAction] = field(default_factory=list)
    batch_results: list[ResolutionResult] = field(default_factory=list)
    batch_maps: list[ResolvedEntityMap] = field(default_factory=list)


class LLMResolutionProposalAgent:
    """Collect model-selected actions without performing graph operations."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        router: ModelRouter | None = None,
        model: str | None = None,
        session_max_tool_calls: int = 50,
        batch_size: int = 5,
    ) -> None:
        self.provider = provider
        self.router = router
        self.model = model
        try:
            configured_limit = int(session_max_tool_calls)
        except (TypeError, ValueError):
            configured_limit = 50
        try:
            configured_batch_size = int(batch_size)
        except (TypeError, ValueError):
            configured_batch_size = 5
        self.session_max_tool_calls = max(1, configured_limit)
        self.batch_size = max(1, configured_batch_size)

    def propose(
        self,
        *,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
    ) -> list[ResolutionToolAction] | LLMSessionAwaitingTool:
        proposal = self._run_proposals(
            step=step,
            source_text=source_text,
            context=context,
            candidate_graph=candidate_graph,
            packets=packets,
        )
        if isinstance(proposal, LLMSessionAwaitingTool):
            return proposal
        if not proposal.actions:
            raise ValueError(
                f"Resolution step '{step.value}' returned no action tool call. "
                "The backend will not infer a fallback action."
            )
        log_event(
            logger,
            "ingestion.resolution.proposal.received",
            component="ingestion",
            resolution_step=step.value,
            action_count=len(proposal.actions),
            action_tools=[str(action.tool_name) for action in proposal.actions],
        )
        return proposal.actions

    def _run_proposals(
        self,
        *,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket],
        start_batch: int = 0,
        initial_actions: Iterable[ResolutionToolAction] = (),
        initial_results: Iterable[ResolutionResult] = (),
        initial_maps: Iterable[ResolvedEntityMap] = (),
        continuation: LLMSessionContinuation | None = None,
        compile_batches: bool = False,
    ) -> _ResolutionProposalRun | LLMSessionAwaitingTool:
        toolbox = build_resolution_toolbox(step)
        step_candidates = self._step_candidates(step, candidate_graph)
        log_event(
            logger,
            "ingestion.resolution.proposal.request",
            component="ingestion",
            resolution_step=step.value,
            candidate_count=len(step_candidates),
            lookup_packet_count=len(packets),
            lookup_statuses=[str(packet.lookup.status) for packet in packets],
            available_tools=sorted(toolbox.tools_by_name),
        )
        actions = list(initial_actions)
        proposal = _ResolutionProposalRun(
            actions=actions,
            batch_results=list(initial_results),
            batch_maps=list(initial_maps),
        )
        session_candidate_refs = self._all_candidate_refs(candidate_graph)
        request_context = AIRequestContext(
            purpose=f"ingestion_resolution_{step.value}",
            source_id=context.source_id,
            metadata={"resolution_step": step.value},
        )
        route = (
            self.router.route(request_context.purpose or "ingestion_resolution", request_context)
            if self.router
            else None
        )
        for batch_start in range(start_batch, len(step_candidates), self.batch_size):
            batch = step_candidates[batch_start : batch_start + self.batch_size]
            prompt = self._system_prompt(
                step,
                build_other_planned_context_packet(
                    candidate_graph,
                    excluded_refs=self._candidate_refs(batch),
                ),
                owner_prompt_block(context.owner_snapshot),
            )
            # A resumed first batch already carries actions from earlier clarification
            # continuations. Validate the complete current-batch accumulator, not only
            # the actions captured during the latest provider invocation.
            action_start = (
                0 if continuation is not None and batch_start == start_batch else len(actions)
            )
            result = self._run_batch(
                step=step,
                source_text=source_text,
                context=context,
                packets=packets,
                batch=batch,
                batch_start=batch_start,
                actions=actions,
                toolbox=toolbox,
                prompt=prompt,
                route=route,
                request_context=request_context,
                continuation=continuation if batch_start == start_batch else None,
            )
            batch_refs = self._candidate_refs(batch)
            result = self._repair_incomplete_batch(
                result=result,
                step=step,
                source_text=source_text,
                context=context,
                candidate_graph=candidate_graph,
                packets=packets,
                batch=batch,
                batch_start=batch_start,
                actions=actions,
                action_start=action_start,
                batch_refs=batch_refs,
                toolbox=toolbox,
                prompt=prompt,
                route=route,
                request_context=request_context,
            )
            if isinstance(result, LLMSessionAwaitingTool):
                return self._with_resolution_state(result, proposal)
            if not isinstance(result, LLMSessionCompleted):
                raise ValueError(f"Resolution step '{step.value}' failed: {result.kind}")
            batch_actions = actions[action_start:]
            if compile_batches:
                batch_result, batch_map = self._compile_batch(
                    actions=batch_actions,
                    batch=batch,
                    packets=packets,
                    candidate_graph=candidate_graph,
                    registry_snapshot=context.reference_registry_snapshot,
                    session_candidate_refs=session_candidate_refs,
                )
                proposal.batch_results.append(batch_result)
                proposal.batch_maps.append(batch_map)
        return proposal

    def resume_nodes(
        self,
        *,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
        continuation: LLMSessionContinuation,
        answer_text: str,
    ) -> tuple[ResolvedEntityMap, ResolutionResult] | LLMSessionAwaitingTool:
        """Resume the paused node-resolution session after a user answer."""

        if not context.reference_registry_snapshot:
            raise ValueError("Node resolution requires the active reference registry snapshot.")
        pending_call = continuation.pending_tool_call
        doubts = pending_call.arguments.get("doubts") or []
        candidate_ref = ""
        if doubts and isinstance(doubts[0], dict):
            refs = doubts[0].get("refs") or []
            candidate_ref = str(refs[0] if refs else "")
        step_candidates = self._step_candidates(ResolutionStep.NODE, candidate_graph)
        candidate_index = next(
            (
                index
                for index, candidate in enumerate(step_candidates)
                if candidate.local_ref == candidate_ref
            ),
            None,
        )
        if candidate_index is None:
            raise ValueError(
                f"Clarification candidate ref '{candidate_ref}' is not present in the "
                "current node-resolution session."
            )
        batch_start = candidate_index - (candidate_index % self.batch_size)
        actions = self._actions_from_events(continuation)
        tool_result = ToolResult(
            status="ok",
            output=f"User clarification answer: {answer_text.strip()}",
            data={
                "operation": "ask_clarification",
                "answer": answer_text.strip(),
            },
        )
        resumed = continuation_with_tool_result(continuation, tool_result)
        completed_results, completed_maps = self._continuation_batches(continuation)
        proposal = self._run_proposals(
            step=ResolutionStep.NODE,
            source_text=source_text,
            context=context,
            candidate_graph=candidate_graph,
            packets=packets,
            start_batch=batch_start,
            initial_actions=actions,
            initial_results=completed_results,
            initial_maps=completed_maps,
            continuation=resumed,
            compile_batches=True,
        )
        if isinstance(proposal, LLMSessionAwaitingTool):
            return proposal
        return self._finalize_proposals(candidate_graph, proposal)

    def _repair_incomplete_batch(
        self,
        *,
        result: LLMSessionCompleted | LLMSessionAwaitingTool,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket],
        batch: Sequence[Any],
        batch_start: int,
        actions: list[ResolutionToolAction],
        action_start: int,
        batch_refs: set[str],
        toolbox: Any,
        prompt: str,
        route: Any,
        request_context: AIRequestContext,
    ) -> LLMSessionCompleted | LLMSessionAwaitingTool:
        """Continue the same session when a terminal turn omits batch actions."""

        if isinstance(result, LLMSessionAwaitingTool):
            return result
        if not isinstance(result, LLMSessionCompleted):
            raise ValueError(f"Resolution session failed: {result.kind}")

        previous_missing: set[str] | None = None
        tool_calls_used = len(result.tool_events)
        current = result
        while True:
            current_refs = {action.candidate_ref for action in actions[action_start:]}
            missing = batch_refs - current_refs
            if not missing:
                return current
            if missing == previous_missing:
                raise ResolutionProposalValidationError(
                    [self._missing_action_message(missing, batch_refs)]
                )
            previous_missing = set(missing)
            remaining_budget = self.session_max_tool_calls - tool_calls_used
            if remaining_budget <= 0:
                raise ResolutionProposalValidationError(
                    [
                        self._missing_action_message(missing, batch_refs)
                        + " The session tool-call budget has been exhausted."
                    ]
                )
            mapping = {
                name: self._capture_handler(step, name, actions) for name in toolbox.tools_by_name
            }
            current = self.provider.run_session(
                LLMSessionRequest(
                    system_prompt=prompt,
                    messages=[
                        *current.messages,
                        ChatMessage(
                            role="user",
                            content=self._missing_action_message(missing, batch_refs),
                        ),
                    ],
                    model=self.model or (route.model if route else None),
                    temperature=0.1,
                    toolbox=toolbox,
                    tools_mapping=mapping,
                    max_tool_calls=remaining_budget,
                    session_id=current.session_id,
                    context=request_context,
                    metadata={
                        "resolution_batch_start": batch_start,
                        "resolution_batch_size": len(batch),
                        "resolution_repair": True,
                        "source_text": source_text,
                        "candidate_graph_id": candidate_graph.candidate_graph_id,
                        "packet_count": len(packets),
                    },
                )
            )
            if isinstance(current, LLMSessionAwaitingTool):
                return current
            tool_calls_used += len(current.tool_events)

    @staticmethod
    def _missing_action_message(
        missing_refs: set[str],
        batch_refs: set[str],
    ) -> str:
        completed_refs = sorted(batch_refs - missing_refs)
        return (
            "Your last assistant turn was incomplete for the current resolution batch. "
            f"Completed action refs: {', '.join(completed_refs) or 'none'}. "
            "Candidates still requiring exactly one terminal action: "
            f"{', '.join(sorted(missing_refs))}. Use the available resolution tools now. "
            "Do not finish with prose until every supplied candidate has one terminal action."
        )

    def _run_batch(
        self,
        *,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        packets: Sequence[EntityLookupContextPacket],
        batch: Sequence[Any],
        batch_start: int,
        actions: list[ResolutionToolAction],
        toolbox: Any,
        prompt: str,
        route: Any,
        request_context: AIRequestContext,
        continuation: LLMSessionContinuation | None = None,
    ) -> LLMSessionCompleted | LLMSessionAwaitingTool:
        batch_refs = {
            candidate.local_ref for candidate in batch if getattr(candidate, "local_ref", None)
        }
        batch_packets = [packet for packet in packets if packet.candidate_ref in batch_refs]
        input_payload = {
            "goal": (
                "Resolve this candidate batch with exactly one terminal action per supplied "
                "candidate. Other planned references are evidence or endpoint context only."
            ),
            "candidate_actions": [self._model_candidate_payload(candidate) for candidate in batch],
            "identity_lookup_packets": [
                packet.model_dump(mode="json", exclude_none=True) for packet in batch_packets
            ],
        }
        mapping = {
            name: self._capture_handler(step, name, actions) for name in toolbox.tools_by_name
        }
        if continuation is None:
            messages = [
                *self._session_history_messages(context, source_text),
                ChatMessage(
                    role="user",
                    content=(f"```json\n{json.dumps(input_payload, ensure_ascii=False)}\n```"),
                ),
            ]
        else:
            messages = list(continuation.messages)
        return self.provider.run_session(
            LLMSessionRequest(
                system_prompt=prompt,
                messages=messages,
                model=self.model or (route.model if route else None),
                temperature=0.1,
                toolbox=toolbox,
                tools_mapping=mapping,
                max_tool_calls=self.session_max_tool_calls,
                session_id=(
                    continuation.session_id
                    if continuation is not None
                    else f"resolution-{context.source_id or 'run'}-{step.value}-{batch_start}"
                ),
                context=request_context,
                continuation=continuation,
            )
        )

    @staticmethod
    def _actions_from_events(
        continuation: LLMSessionContinuation,
    ) -> list[ResolutionToolAction]:
        actions: list[ResolutionToolAction] = []
        for event in continuation.tool_events:
            data = event.result.data
            if not isinstance(data, dict) or not isinstance(data.get("action"), dict):
                continue
            actions.append(ResolutionToolAction.model_validate(data["action"]))
        return actions

    def resolve_nodes(
        self,
        *,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
    ) -> tuple[ResolvedEntityMap, ResolutionResult] | LLMSessionAwaitingTool:
        if not context.reference_registry_snapshot:
            raise ValueError("Node resolution requires the active reference registry snapshot.")
        proposal = self._run_proposals(
            step=ResolutionStep.NODE,
            source_text=source_text,
            context=context,
            candidate_graph=candidate_graph,
            packets=packets,
            compile_batches=True,
        )
        if isinstance(proposal, LLMSessionAwaitingTool):
            return proposal
        return self._finalize_proposals(candidate_graph, proposal)

    @staticmethod
    def _candidate_refs(candidates: Sequence[Any]) -> set[str]:
        return {
            candidate.local_ref for candidate in candidates if getattr(candidate, "local_ref", None)
        }

    def _compile_batch(
        self,
        *,
        actions: Sequence[ResolutionToolAction],
        batch: Sequence[Any],
        packets: Sequence[EntityLookupContextPacket],
        candidate_graph: CandidateMemoryGraph,
        registry_snapshot: dict[str, Any],
        session_candidate_refs: set[str],
    ) -> tuple[ResolutionResult, ResolvedEntityMap]:
        registry = RunReferenceRegistry.from_snapshot(registry_snapshot)
        compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
        batch_refs = self._candidate_refs(batch)
        batch_packets = [packet for packet in packets if packet.candidate_ref in batch_refs]
        result = compiler.compile(
            actions,
            candidate_graph=candidate_graph,
            packets=batch_packets,
            supplied_candidate_refs=session_candidate_refs,
            required_candidate_refs=batch_refs,
            action_candidate_refs=batch_refs,
        )
        return (
            result,
            compiler.build_entity_map(
                candidate_graph,
                result,
                candidate_refs=batch_refs,
            ),
        )

    @staticmethod
    def _with_resolution_state(
        pending: LLMSessionAwaitingTool,
        proposal: _ResolutionProposalRun,
    ) -> LLMSessionAwaitingTool:
        continuation = pending.continuation.model_copy(
            update={
                "metadata": {
                    **pending.continuation.metadata,
                    "resolution_completed_results": [
                        result.model_dump(mode="json") for result in proposal.batch_results
                    ],
                    "resolution_completed_maps": [
                        entity_map.model_dump(mode="json") for entity_map in proposal.batch_maps
                    ],
                }
            }
        )
        return pending.model_copy(update={"continuation": continuation}, deep=True)

    @staticmethod
    def _continuation_batches(
        continuation: LLMSessionContinuation,
    ) -> tuple[list[ResolutionResult], list[ResolvedEntityMap]]:
        results = [
            ResolutionResult.model_validate(item)
            for item in continuation.metadata.get("resolution_completed_results", [])
            if isinstance(item, dict)
        ]
        maps = [
            ResolvedEntityMap.model_validate(item)
            for item in continuation.metadata.get("resolution_completed_maps", [])
            if isinstance(item, dict)
        ]
        if len(results) != len(maps):
            raise ValueError("Resolution continuation has incomplete completed-batch state.")
        return results, maps

    @staticmethod
    def _finalize_proposals(
        candidate_graph: CandidateMemoryGraph,
        proposal: _ResolutionProposalRun,
    ) -> tuple[ResolvedEntityMap, ResolutionResult]:
        expected_refs = [entity.local_ref for entity in candidate_graph.candidate_entities]
        decisions = [decision for result in proposal.batch_results for decision in result.decisions]
        decisions_by_ref: dict[str, list[Any]] = {}
        for decision in decisions:
            decisions_by_ref.setdefault(decision.candidate_ref, []).append(decision)
        duplicate_refs = sorted(
            ref for ref, entries in decisions_by_ref.items() if len(entries) > 1
        )
        missing_refs = sorted(set(expected_refs) - set(decisions_by_ref))
        if duplicate_refs or missing_refs:
            errors: list[str] = []
            if duplicate_refs:
                errors.append(
                    "Resolution coverage contains duplicate completed batches for: "
                    f"{', '.join(duplicate_refs)}."
                )
            if missing_refs:
                errors.append(
                    "Resolution coverage is incomplete. Missing completed batch results for: "
                    f"{', '.join(missing_refs)}."
                )
            raise ValueError(" ".join(errors))

        entries_by_ref = {
            entry.local_ref: entry
            for entity_map in proposal.batch_maps
            for entry in entity_map.entries
        }
        missing_map_refs = sorted(set(expected_refs) - set(entries_by_ref))
        if missing_map_refs:
            raise ValueError(
                f"Resolution entity-map coverage is incomplete for: {', '.join(missing_map_refs)}."
            )
        merged_result = ResolutionResult(
            decisions=[decisions_by_ref[ref][0] for ref in expected_refs],
            metadata={
                "policy": "llm_selected_action_backend_validated_per_batch",
                "validated_tool_actions": [
                    action
                    for result in proposal.batch_results
                    for action in result.metadata.get("validated_tool_actions", [])
                ],
            },
        )
        merged_map = ResolvedEntityMap(
            entries=[entries_by_ref[ref] for ref in expected_refs],
            notes=["Merged from independently validated resolution batches."],
        )
        return merged_map, merged_result

    def _capture_handler(
        self,
        step: ResolutionStep,
        name: str,
        actions: list[ResolutionToolAction],
    ) -> Any:
        def capture(**kwargs: Any) -> ToolResult:
            if name == ResolutionToolName.ASK_CLARIFICATION.value:
                handoff = ClarificationHandoffRequest(
                    doubts=kwargs.get("doubts") or [],
                    invoker_state_id=step.value,
                )
                return ToolResult(
                    status="pending",
                    output="Clarification agent handoff is awaiting user interaction.",
                    data={
                        "operation": "ask_clarification",
                        "handoff": handoff.model_dump(mode="json", exclude_none=True),
                    },
                )
            try:
                action = ResolutionToolAction(
                    step=step,
                    tool_name=ResolutionToolName(name),
                    **kwargs,
                )
            except Exception as exc:
                return ToolResult(
                    status="error",
                    output=f"Invalid {name} proposal: {exc}",
                )
            actions.append(action)
            return ToolResult(
                status="accepted",
                output=(
                    f"{name} proposal accepted for backend validation. "
                    "Continue only with supplied refs."
                ),
                data={"action": action.model_dump(mode="json", exclude_none=True)},
            )

        return capture

    @staticmethod
    def _step_candidates(
        step: ResolutionStep,
        candidate_graph: CandidateMemoryGraph,
    ) -> list[Any]:
        if step == ResolutionStep.NODE:
            return list(candidate_graph.candidate_entities)
        if step == ResolutionStep.MEMORY:
            return [*candidate_graph.memory_logs, *candidate_graph.candidate_profile_memories]
        return [
            *candidate_graph.candidate_relationships,
            *candidate_graph.candidate_relationship_contexts,
        ]

    @staticmethod
    def _model_candidate_payload(candidate: Any) -> dict[str, Any]:
        payload = candidate.model_dump(mode="json", exclude_none=True)
        return {
            key: value
            for key, value in payload.items()
            if not key.endswith("_id") and key not in {"metadata", "source_refs", "evidence_refs"}
        }

    @classmethod
    def _all_candidate_refs(cls, candidate_graph: CandidateMemoryGraph) -> set[str]:
        candidates = [
            *candidate_graph.candidate_entities,
            *candidate_graph.memory_logs,
            *candidate_graph.candidate_profile_memories,
            *candidate_graph.candidate_relationships,
            *candidate_graph.candidate_relationship_contexts,
            *candidate_graph.candidate_claims,
            *candidate_graph.candidate_perceptions,
            *candidate_graph.candidate_metadata_patches,
        ]
        return cls._candidate_refs(candidates)

    @staticmethod
    def _system_prompt(
        step: ResolutionStep,
        other_context: str = "",
        owner_context: str = "",
    ) -> str:
        context_blocks = "".join(
            f"\n\n{block}" for block in (owner_context, other_context) if block
        )
        return (
            "You are the semantic resolution agent for an ingestion step. The backend "
            "owns graph lookup, reference translation, validation, and writing. Select "
            f"one or more actions only from the {step.value} toolbox. Use only refs in "
            "the supplied context; never invent persisted IDs or aliases. Contextual "
            "matches are evidence, not decisions. Prior clarification messages are part "
            "of the transcript: treat an explicit user answer as current-run evidence and "
            "do not repeat the same question unless the answer leaves the identity unresolved. "
            "Use the source, history, and summaries to decide. If uncertainty remains, "
            "call ask_clarification. Stable Person "
            "traits belong in profile-memory actions, never direct Person properties. "
            "Use OWNER for first-person references and never create an owner. For every "
            "ambiguous entity, ask for clarification when additional identity information "
            "may be useful. After the user answers, apply the answer to the structured "
            "candidate payload before creating or updating a node; do not put it only in "
            "the reason. If the answer remains incomplete but the user has not asked to "
            "discard or defer the candidate, use the best supported ambiguous identity. "
            "Use defer_or_ignore only after an explicit user request not to save or defer. "
            "For every "
            "candidate listed in this step, invoke exactly one terminal action tool: a "
            "mutation, defer_or_ignore, or ask_clarification. Do not finish with prose "
            "only and do not omit a candidate action." + context_blocks
        )

    @staticmethod
    def _session_history_messages(
        context: IngestionContextPackage,
        source_text: str | None,
    ) -> list[ChatMessage]:
        messages = LLMResolutionProposalAgent._clarification_history_messages(context)
        normalized_source = (source_text or "").strip()
        if normalized_source and not any(
            message.role == "user" and message.content.strip() == normalized_source
            for message in messages
        ):
            insert_at = next(
                (
                    index
                    for index, message in enumerate(messages)
                    if message.role == "assistant" and message.content.startswith("Clarification")
                ),
                len(messages),
            )
            messages.insert(insert_at, ChatMessage(role="user", content=normalized_source))
        return messages

    @staticmethod
    def _clarification_history_messages(
        context: IngestionContextPackage,
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        for item in context.metadata.get("model_facing_history") or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            content = item.get("content")
            if role not in {"user", "assistant", "developer", "tool"} or not content:
                continue
            messages.append(ChatMessage(role=role, content=str(content)))
        return messages
