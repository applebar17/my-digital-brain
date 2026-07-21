"""LLM proposal boundary for context-driven identity resolution."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.protocols import ModelRouter, ToolCallingLLMProvider
from my_digital_brain.ai.schemas import AIRequestContext, ChatMessage, ChatRequest
from my_digital_brain.clarification import ClarificationService
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
from my_digital_brain.ingestion.resolution_proposals import (
    ResolutionProposalCompiler,
    ResolutionProposalValidator,
)
from my_digital_brain.ingestion.resolution_toolboxes import build_resolution_toolbox

logger = logging.getLogger(__name__)


class LLMResolutionProposalAgent:
    """Collect model-selected actions without performing graph operations."""

    def __init__(
        self,
        provider: ToolCallingLLMProvider,
        *,
        router: ModelRouter | None = None,
        model: str | None = None,
        max_tool_calls: int = 10,
        clarification_service: ClarificationService | None = None,
    ) -> None:
        self.provider = provider
        self.router = router
        self.model = model
        try:
            configured_limit = int(max_tool_calls)
        except (TypeError, ValueError):
            configured_limit = 10
        self.max_tool_calls = min(10, max(1, configured_limit))
        self.clarification_service = clarification_service or ClarificationService()

    def propose(
        self,
        *,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
    ) -> list[ResolutionToolAction]:
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
        actions: list[ResolutionToolAction] = []
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
        prompt = self._system_prompt(step)
        for batch_start in range(0, len(step_candidates), self.max_tool_calls):
            batch = step_candidates[batch_start : batch_start + self.max_tool_calls]
            batch_refs = {
                candidate.local_ref
                for candidate in batch
                if getattr(candidate, "local_ref", None)
            }
            batch_packets = [packet for packet in packets if packet.candidate_ref in batch_refs]
            input_payload = {
                "source_text": source_text,
                "owner_context": owner_prompt_block(context.owner_snapshot),
                "candidate_actions": [
                    self._model_candidate_payload(candidate)
                    for candidate in batch
                ],
                "identity_lookup_packets": [
                    packet.model_dump(mode="json", exclude_none=True)
                    for packet in batch_packets
                ],
                "available_tools": sorted(toolbox.tools_by_name),
            }
            mapping = {
                name: self._capture_handler(step, name, actions)
                for name in toolbox.tools_by_name
            }
            self.provider.generate_chat_with_tools(
                ChatRequest(
                    model=self.model or (route.model if route else None),
                    temperature=0.1,
                    messages=[
                        ChatMessage(role="system", content=prompt),
                        ChatMessage(
                            role="user",
                            content=(
                                "```json\n"
                                f"{json.dumps(input_payload, ensure_ascii=False)}\n```"
                            ),
                        ),
                    ],
                    context=request_context,
                ),
                toolbox=toolbox,
                tools_mapping=mapping,
                max_tool_calls=len(batch),
            )
        if not actions:
            raise ValueError(
                f"Resolution step '{step.value}' returned no action tool call. "
                "The backend will not infer a fallback action."
            )
        log_event(
            logger,
            "ingestion.resolution.proposal.received",
            component="ingestion",
            resolution_step=step.value,
            action_count=len(actions),
            action_tools=[str(action.tool_name) for action in actions],
        )
        return actions

    def resolve_nodes(
        self,
        *,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
    ) -> tuple[ResolvedEntityMap, ResolutionResult]:
        if not context.reference_registry_snapshot:
            raise ValueError("Node resolution requires the active reference registry snapshot.")
        registry = RunReferenceRegistry.from_snapshot(context.reference_registry_snapshot)
        actions = self.propose(
            step=ResolutionStep.NODE,
            source_text=source_text,
            context=context,
            candidate_graph=candidate_graph,
            packets=packets,
        )
        compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
        result = compiler.compile(
            actions,
            candidate_graph=candidate_graph,
            packets=packets,
        )
        return compiler.build_entity_map(candidate_graph, result), result

    def _capture_handler(
        self,
        step: ResolutionStep,
        name: str,
        actions: list[ResolutionToolAction],
    ) -> Any:
        def capture(**kwargs: Any) -> ToolResult:
            if name == ResolutionToolName.ASK_CLARIFICATION.value:
                return self.clarification_service.ask(
                    reason=str(kwargs.get("reason") or "The current context is ambiguous."),
                    questions=[
                        {
                            "question": kwargs.get("question"),
                            "options": [
                                {"label": option}
                                for option in kwargs.get("options", [])
                                if str(option).strip()
                            ],
                        }
                    ],
                    target_refs=[str(kwargs["candidate_ref"])],
                    state_id=step.value,
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
            if not key.endswith("_id")
            and key not in {"metadata", "source_refs", "evidence_refs"}
        }

    @staticmethod
    def _system_prompt(step: ResolutionStep) -> str:
        return (
            "You are the semantic resolution agent for an ingestion step. The backend "
            "owns graph lookup, reference translation, validation, and writing. Select "
            f"one or more actions only from the {step.value} toolbox. Use only refs in "
            "the supplied context; never invent persisted IDs or aliases. Contextual "
            "matches are evidence, not decisions. Use the source, history, and summaries "
            "to decide. If uncertainty remains, call ask_clarification. Stable Person "
            "traits belong in profile-memory actions, never direct Person properties. "
            "Use OWNER for first-person references and never create an owner. For every "
            "candidate listed in this step, invoke exactly one terminal action tool: a "
            "mutation, defer_or_ignore, or ask_clarification. Do not finish with prose "
            "only and do not omit a candidate action."
        )
