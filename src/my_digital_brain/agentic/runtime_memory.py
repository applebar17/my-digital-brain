from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic.contexts import (
    ConversationContext,
    EdgeMemoryPlan,
    MemoryIngestionContext,
    MemoryIngestionReasoning,
    MemoryIngestionResultContext,
    MemoryLogMemoryPlan,
    MemoryPlan,
    NodeMemoryPlan,
)
from my_digital_brain.agentic.enums import AgenticStateId, MemoryPlanActionType, MemoryPlanningPhase
from my_digital_brain.agentic.planning_contracts import (
    PlanningPurposeGuidelines,
    PlanningTransformContext,
)
from my_digital_brain.agentic.runtime_helpers import (
    _collect_memory_plan_refs,
    _compact_state_trace,
    _memory_ingestion_error_result,
)
from my_digital_brain.agentic.runtime_models import (
    AgenticRunResult,
    AgenticStateInvocation,
    AgenticStateRunResult,
)
from my_digital_brain.agentic.tools import AgenticToolExecutionContext


@dataclass(slots=True)
class MemoryIngestionRuntimeService:
    runtime: Any

    def run(
        self,
        payload: MemoryIngestionContext,
        execution_context: AgenticToolExecutionContext,
        conversation_context: ConversationContext,
    ) -> AgenticRunResult:
        execution_context.agentic_runtime = self.runtime
        execution_context.conversation_context = conversation_context
        execution_context.state_id = AgenticStateId.MEMORY_INGESTION.value
        state_results: list[AgenticStateRunResult] = []
        compact_trace: list[dict[str, Any]] = []

        reasoning_result = self.runtime.state_runner.run_structured_state(
            AgenticStateInvocation(
                state_id=AgenticStateId.MEMORY_INGESTION,
                context_payload=payload,
                execution_context=execution_context,
                metadata={
                    "structured_output": True,
                    "output_schema": "MemoryIngestionReasoning",
                    "phase": "reasoning_inventory",
                },
            ),
            output_schema=MemoryIngestionReasoning,
        )
        state_results.append(reasoning_result)
        compact_trace.append(_compact_state_trace(reasoning_result))
        if reasoning_result.status != "ok" or reasoning_result.structured_output is None:
            return _memory_ingestion_error_result(state_results, compact_trace, reasoning_result)

        reasoning = MemoryIngestionReasoning.model_validate(reasoning_result.structured_output)
        current_payload = payload.model_copy(update={"reasoning": reasoning}, deep=True)

        node_plan_result = self._run_memory_phase_plan(
            current_payload,
            execution_context,
            phase=MemoryPlanningPhase.NODES,
            prompt_id="memory_node_planning",
            output_schema=NodeMemoryPlan,
        )
        state_results.append(node_plan_result)
        compact_trace.append(_compact_state_trace(node_plan_result))
        if node_plan_result.status != "ok" or node_plan_result.structured_output is None:
            return _memory_ingestion_error_result(state_results, compact_trace, node_plan_result)
        node_plan = NodeMemoryPlan.model_validate(node_plan_result.structured_output)
        current_payload = current_payload.model_copy(
            update={
                "node_plan": node_plan,
                "node_plan_packet": node_plan.node_plan_packet,
                "metadata": {
                    **current_payload.metadata,
                    "node_plan": node_plan.model_dump(mode="json", exclude_none=True),
                    "node_plan_packet": node_plan.node_plan_packet.model_dump(
                        mode="json", exclude_none=True
                    ),
                },
            },
            deep=True,
        )
        node_action_result = self._execute_memory_plan_actions(
            node_plan.steps,
            execution_context,
            conversation_context,
            current_payload,
        )
        if node_action_result is not None:
            state_results.extend(node_action_result.state_results)
            compact_trace.extend(node_action_result.compact_trace or [])
            if node_action_result.status in {"interrupted", "pending"}:
                node_action_result.state_results = state_results
                node_action_result.compact_trace = compact_trace
                return node_action_result

        memory_plan_result = self._run_memory_phase_plan(
            current_payload,
            execution_context,
            phase=MemoryPlanningPhase.MEMORY_LOGS,
            prompt_id="memory_log_planning",
            output_schema=MemoryLogMemoryPlan,
        )
        state_results.append(memory_plan_result)
        compact_trace.append(_compact_state_trace(memory_plan_result))
        if memory_plan_result.status != "ok" or memory_plan_result.structured_output is None:
            return _memory_ingestion_error_result(state_results, compact_trace, memory_plan_result)
        memory_plan = MemoryLogMemoryPlan.model_validate(memory_plan_result.structured_output)
        current_payload = current_payload.model_copy(
            update={
                "memory_plan": memory_plan,
                "memory_plan_packet": memory_plan.memory_plan_packet,
                "metadata": {
                    **current_payload.metadata,
                    "memory_plan": memory_plan.model_dump(mode="json", exclude_none=True),
                    "memory_plan_packet": memory_plan.memory_plan_packet.model_dump(
                        mode="json", exclude_none=True
                    ),
                },
            },
            deep=True,
        )
        memory_action_result = self._execute_memory_plan_actions(
            memory_plan.steps,
            execution_context,
            conversation_context,
            current_payload,
        )
        if memory_action_result is not None:
            state_results.extend(memory_action_result.state_results)
            compact_trace.extend(memory_action_result.compact_trace or [])
            if memory_action_result.status in {"interrupted", "pending"}:
                memory_action_result.state_results = state_results
                memory_action_result.compact_trace = compact_trace
                return memory_action_result

        edge_plan_result = self._run_memory_phase_plan(
            current_payload,
            execution_context,
            phase=MemoryPlanningPhase.EDGES,
            prompt_id="memory_edge_planning",
            output_schema=EdgeMemoryPlan,
        )
        state_results.append(edge_plan_result)
        compact_trace.append(_compact_state_trace(edge_plan_result))
        if edge_plan_result.status != "ok" or edge_plan_result.structured_output is None:
            return _memory_ingestion_error_result(state_results, compact_trace, edge_plan_result)
        edge_plan = EdgeMemoryPlan.model_validate(edge_plan_result.structured_output)
        current_payload = current_payload.model_copy(
            update={
                "edge_plan": edge_plan,
                "metadata": {
                    **current_payload.metadata,
                    "edge_plan": edge_plan.model_dump(mode="json", exclude_none=True),
                },
            },
            deep=True,
        )
        edge_action_result = self._execute_memory_plan_actions(
            edge_plan.steps,
            execution_context,
            conversation_context,
            current_payload,
        )
        if edge_action_result is not None:
            state_results.extend(edge_action_result.state_results)
            compact_trace.extend(edge_action_result.compact_trace or [])
            if edge_action_result.status in {"interrupted", "pending"}:
                edge_action_result.state_results = state_results
                edge_action_result.compact_trace = compact_trace
                return edge_action_result

        aggregated_plan = MemoryPlan(
            steps=[*node_plan.steps, *memory_plan.steps, *edge_plan.steps],
            metadata={
                "reasoning": reasoning.model_dump(mode="json", exclude_none=True),
                "node_plan_packet": node_plan.node_plan_packet.model_dump(
                    mode="json", exclude_none=True
                ),
                "memory_plan_packet": memory_plan.memory_plan_packet.model_dump(
                    mode="json", exclude_none=True
                ),
            },
        )
        result_context = MemoryIngestionResultContext(
            plan=aggregated_plan,
            summary="Memory ingestion planning completed through nodes, memory_logs, and edges.",
            phase_summaries=[node_plan.summary, memory_plan.summary, edge_plan.summary],
            created_refs=_collect_memory_plan_refs(aggregated_plan, "created_refs"),
            updated_refs=_collect_memory_plan_refs(aggregated_plan, "updated_refs"),
            affected_graph_ids=_collect_memory_plan_refs(aggregated_plan, "affected_graph_ids"),
            ref_context_delta={
                "node_plan_packet": node_plan.node_plan_packet.model_dump(
                    mode="json", exclude_none=True
                ),
                "memory_plan_packet": memory_plan.memory_plan_packet.model_dump(
                    mode="json", exclude_none=True
                ),
            },
            diagnostics=compact_trace,
        )
        final_result = AgenticStateRunResult(
            state_id=AgenticStateId.MEMORY_INGESTION,
            assistant_text=result_context.summary,
            structured_output=result_context.model_dump(mode="json", exclude_none=True),
            terminal=True,
            status="ok",
            metadata={"structured_output_schema": "MemoryIngestionResultContext"},
        )
        state_results.append(final_result)
        compact_trace.append(_compact_state_trace(final_result))
        return AgenticRunResult(
            final_text=result_context.summary,
            visited_states=[result.state_id for result in state_results],
            state_results=state_results,
            status="ok",
            compact_trace=compact_trace,
        )

    def _run_memory_phase_plan(
        self,
        payload: MemoryIngestionContext,
        execution_context: AgenticToolExecutionContext,
        *,
        phase: MemoryPlanningPhase,
        prompt_id: str,
        output_schema: type[BaseModel],
    ) -> AgenticStateRunResult:
        context = PlanningTransformContext(
            purpose=PlanningPurposeGuidelines(
                purpose_id=f"memory_ingestion_{phase.value}_planning",
                goal=f"Plan the {phase.value} phase for memory ingestion.",
                focus_areas=[phase.value, "refs", "compact_handoff_packets"],
                instructions=[
                    "Use refs only where refs are required.",
                    "Return the dedicated phase schema.",
                    "Do not write or mutate graph state.",
                ],
                output_usage=output_schema.__name__,
            ),
            input_context={
                "reasoning_inventory_packet": (
                    payload.reasoning.model_dump(mode="json", exclude_none=True)
                    if payload.reasoning is not None
                    else None
                ),
                "ref_context_packet": (
                    payload.ref_context.model_facing_packet()
                    if payload.ref_context is not None
                    else []
                ),
                "ref_packets": payload.ref_packets,
                "reasoning_packets": payload.reasoning_packets,
                "node_plan_packet": (
                    payload.node_plan_packet.model_dump(mode="json", exclude_none=True)
                    if payload.node_plan_packet is not None
                    else None
                ),
                "memory_plan_packet": (
                    payload.memory_plan_packet.model_dump(mode="json", exclude_none=True)
                    if payload.memory_plan_packet is not None
                    else None
                ),
                "irrelevant_details_packet": [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in (payload.reasoning.irrelevant_details if payload.reasoning else [])
                ],
                "duplicate_candidate_packets": payload.metadata.get(
                    "duplicate_candidate_packets", []
                ),
                "relationship_candidate_packets": payload.metadata.get(
                    "relationship_candidate_packets", []
                ),
            },
            reasoning_artifact=(
                payload.reasoning.model_dump(mode="json", exclude_none=True)
                if payload.reasoning is not None
                else None
            ),
            conversation=payload.conversation,
            current_time=payload.current_time,
            timezone=payload.timezone,
            prior_tool_outputs=payload.prior_tool_outputs,
            expected_output_schema=output_schema.__name__,
        )
        return self.runtime.state_runner.run_structured_state(
            AgenticStateInvocation(
                state_id=AgenticStateId.PLANNING_CHECKPOINT,
                context_payload=context,
                execution_context=execution_context,
                metadata={
                    "structured_output": True,
                    "output_schema": output_schema.__name__,
                    "phase": phase.value,
                    "prompt_id_override": prompt_id,
                },
            ),
            output_schema=output_schema,
        )

    def _execute_memory_plan_actions(
        self,
        steps: list[Any],
        execution_context: AgenticToolExecutionContext,
        conversation_context: ConversationContext,
        payload: MemoryIngestionContext,
    ) -> AgenticRunResult | None:
        action_results: list[AgenticStateRunResult] = []
        compact_trace: list[dict[str, Any]] = []
        for step in steps:
            for action in step.actions:
                child_state = (
                    AgenticStateId.GRAPH_UPDATE
                    if action.action_type == MemoryPlanActionType.UPDATE_NODE
                    else AgenticStateId.MEMORY_CREATION
                )
                if child_state == AgenticStateId.MEMORY_CREATION:
                    from my_digital_brain.agentic.contexts import MemoryCreationContext

                    child_payload = MemoryCreationContext(
                        conversation=conversation_context,
                        action=action,
                        graph_context=payload.graph_context,
                        current_time=payload.current_time,
                        timezone=payload.timezone,
                        ref_context=payload.ref_context,
                        ref_packets=payload.ref_packets,
                        resolved_clarifications=payload.resolved_clarifications,
                        metadata={
                            "source": "memory_ingestion_phase_plan",
                            "phase": action.metadata.get("phase"),
                        },
                    )
                    tool_name = "run_memory_creation"
                else:
                    from my_digital_brain.agentic.contexts import GraphUpdateContext

                    child_payload = GraphUpdateContext(
                        source_text=str(payload.metadata.get("source_text") or ""),
                        conversation=conversation_context,
                        desired_work=action.rationale or action.payload.get("desired_work"),
                        target_ids=action.target_refs,
                        graph_context=payload.graph_context,
                        current_time=payload.current_time,
                        timezone=payload.timezone,
                        metadata={
                            "action": action.model_dump(mode="json", exclude_none=True),
                            "resolved_clarifications": payload.resolved_clarifications,
                        },
                    )
                    tool_name = "update_memory_graph"
                result = self.runtime.run_child_frame(
                    parent_execution_context=execution_context,
                    conversation_context=conversation_context,
                    child_state=child_state,
                    child_payload=child_payload,
                    tool_name=tool_name,
                )
                state_result = AgenticStateRunResult(
                    state_id=child_state,
                    assistant_text=result.output,
                    terminal=result.status not in {"interrupted", "pending"},
                    status=str(result.status),
                    metadata={"tool_result": result.model_dump(mode="json", exclude_none=True)},
                )
                action_results.append(state_result)
                compact_trace.append(_compact_state_trace(state_result))
                if result.status in {"interrupted", "pending"}:
                    return AgenticRunResult(
                        final_text=result.output,
                        visited_states=[item.state_id for item in action_results],
                        state_results=action_results,
                        status="interrupted",
                        interruption=(result.data if isinstance(result.data, dict) else None),
                        compact_trace=compact_trace,
                    )
        if not action_results:
            return None
        return AgenticRunResult(
            final_text="Memory ingestion actions executed.",
            visited_states=[item.state_id for item in action_results],
            state_results=action_results,
            status="ok" if all(item.status == "ok" for item in action_results) else "error",
            compact_trace=compact_trace,
        )
