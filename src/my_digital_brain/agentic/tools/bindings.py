from __future__ import annotations

import json
import logging
from copy import copy
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic.contexts import (
    GraphContextPackage,
    GraphUpdateContext,
    MemoryCreationContext,
    MemoryIngestionContext,
    MemoryPlanAction,
    QueryRetrievalPlanningContext,
)
from my_digital_brain.agentic.enums import AgenticStateId, RefObjectKind
from my_digital_brain.agentic.refs import RefContext
from my_digital_brain.agentic.runtime_models import AgenticToolEvent
from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.models import ToolError, ToolResult
from my_digital_brain.clarification.contracts import (
    ClarificationHandoffRequest,
    ClarificationSessionInput,
)
from my_digital_brain.clarification.toolbox import ClarificationToolService
from my_digital_brain.core.owner_context import OwnerSnapshot
from my_digital_brain.graph.registry import (
    CORE_RELATIONSHIP_TYPE_SET,
    GRAPH_MUTABLE_NODE_LABELS,
    GRAPH_MUTABLE_RELATIONSHIP_TYPES,
)

GRAPH_UPDATE_CREATABLE_LABELS = frozenset(GRAPH_MUTABLE_NODE_LABELS)

logger = logging.getLogger(__name__)

GRAPH_UPDATE_BLOCKED_RELATIONSHIP_TYPES = (
    CORE_RELATIONSHIP_TYPE_SET - set(GRAPH_MUTABLE_RELATIONSHIP_TYPES)
)


@dataclass(slots=True)
class AgenticToolExecutionContext:
    state_id: str | None = None
    graph_service: Any | None = None
    ingestion_service: Any | None = None
    semantic_search_service: Any | None = None
    vectorization_service: Any | None = None
    chat_store: Any | None = None
    session_id: str | None = None
    channel: str = "web"
    conversation_id: str | None = None
    application_user_id: str | None = None
    graph_owner_id: str | None = None
    owner_snapshot: OwnerSnapshot | None = None
    sender_id: str | None = None
    message_id: str | None = None
    current_text: str | None = None
    conversation_history_refs: list[str] = field(default_factory=list)
    tool_events: list[AgenticToolEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    frame_id: str | None = None
    parent_frame_id: str | None = None
    parent_tool_call_id: str | None = None
    current_tool_call_id: str | None = None
    current_tool_name: str | None = None
    current_tool_arguments: dict[str, Any] = field(default_factory=dict)
    provider_messages: list[dict[str, Any]] = field(default_factory=list)
    agentic_runtime: Any | None = None
    conversation_context: Any | None = None
    current_payload: Any | None = None
    ref_context: RefContext | None = None
    # Retained only while the legacy ingestion service is migrated. Active
    # agentic chat must use ref_context; no new code should populate this.
    reference_registry: Any | None = None


class AgenticToolBindings:
    def __init__(self, context: AgenticToolExecutionContext) -> None:
        self.context = context

    def handler_for(self, handler_key: str):
        handler = getattr(self, f"_handle_{handler_key}", None)
        if handler is None:
            raise ValueError(f"No agentic tool handler registered for key: {handler_key}")
        return handler

    def _handle_query_memory(
        self,
        question: str,
        seed_id: str | None = None,
        desired_view: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        conversation = self._conversation_context()
        retrieval = self._semantic_retrieval(
            question,
            seed_id=seed_id,
            desired_view=desired_view,
            limit=5,
        )
        query_context = QueryRetrievalPlanningContext(
            question=question,
            conversation=conversation,
            seed_aliases={"seed": seed_id} if seed_id else {},
            desired_view=desired_view,
            metadata={
                **(metadata or {}),
                "seed_id": seed_id,
                "retrieval": retrieval,
            },
        )
        return self._run_child_frame(
            tool_name="query_memory",
            state_id=AgenticStateId.MEMORY_QUERY,
            payload=query_context,
        )

    def _handle_ingest_memory(self) -> ToolResult:
        conversation = self._conversation_context()
        source_text = self._source_text_from_context()
        retrieval = self._semantic_retrieval(source_text, limit=5) if source_text else {}
        ref_context = self.context.ref_context or _ref_context_from_retrieval(
            retrieval,
            session_id=self.context.session_id or conversation.context_id,
        )
        if self.context.graph_owner_id:
            _ensure_owner_ref(
                ref_context,
                self.context.graph_owner_id,
                self.context.owner_snapshot,
            )
        graph_context = _graph_context_from_retrieval(retrieval, ref_context=ref_context)
        self.context.ref_context = ref_context
        ingestion_context = MemoryIngestionContext(
            conversation=conversation,
            graph_context=graph_context,
            ref_context=ref_context,
            timezone=conversation.timezone,
            current_time=conversation.current_time,
            metadata={
                "source_text": source_text,
                "retrieval": retrieval,
            },
        )
        return self._run_child_frame(
            tool_name="ingest_memory",
            state_id=AgenticStateId.MEMORY_INGESTION,
            payload=ingestion_context,
        )

    def _handle_run_memory_creation(
        self,
        action_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        action = self._memory_plan_action(action_id, metadata=metadata or {})
        if isinstance(action, ToolResult):
            return action
        conversation = self._conversation_context()
        current_payload = self.context.current_payload
        graph_context = getattr(current_payload, "graph_context", None)
        creation_context = MemoryCreationContext(
            conversation=conversation,
            action=action,
            graph_context=graph_context,
            ref_context=getattr(current_payload, "ref_context", self.context.ref_context),
            timezone=getattr(current_payload, "timezone", conversation.timezone),
            current_time=getattr(current_payload, "current_time", conversation.current_time),
            metadata={"source": "run_memory_creation", **(metadata or {})},
        )
        return self._run_child_frame(
            tool_name="run_memory_creation",
            state_id=AgenticStateId.MEMORY_CREATION,
            payload=creation_context,
        )

    def _handle_update_memory_graph(
        self,
        source_text: str | None = None,
        guidelines: str | None = None,
        desired_work: str | None = None,
        target_ids: list[str] | None = None,
        source_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        resolved_source = (source_text or self._source_text_from_context()).strip()
        if not resolved_source:
            return _update_tool_error(
                "update_memory_graph",
                "missing_source_text",
                "Graph update needs source text from the current frame history.",
                "Retry from a frame with a current user message or pass source_text explicitly.",
                retryable=True,
            )
        update_context = GraphUpdateContext(
            source_text=resolved_source,
            conversation=self._conversation_context(),
            guidelines=guidelines or "Update the memory graph using deterministic tools.",
            desired_work=desired_work,
            target_ids=target_ids or [],
            source_refs=source_refs or [],
            graph_context=getattr(self.context.current_payload, "graph_context", None),
            ref_context=getattr(
                self.context.current_payload,
                "ref_context",
                self.context.ref_context,
            ),
            metadata=metadata or {},
        )
        return self._run_child_frame(
            tool_name="update_memory_graph",
            state_id=AgenticStateId.GRAPH_UPDATE,
            payload=update_context,
        )

    def _run_child_frame(
        self,
        *,
        tool_name: str,
        state_id: AgenticStateId,
        payload: Any,
    ) -> ToolResult:
        runtime = self.context.agentic_runtime
        if runtime is None:
            return _missing_dependency(tool_name, "agentic_runtime")
        conversation = self._conversation_context()
        return runtime.run_child_frame(
            parent_execution_context=self.context,
            conversation_context=conversation,
            child_state=state_id,
            child_payload=payload,
            tool_name=tool_name,
        )

    def _conversation_context(self):
        if self.context.conversation_context is not None:
            return self.context.conversation_context
        from my_digital_brain.agentic.contexts import ConversationContext
        from my_digital_brain.agentic.messages import NeutralConversationMessage

        current_text = self._source_text_from_context() or "Message"
        return ConversationContext(
            current_message=NeutralConversationMessage.user(current_text),
        )

    def _source_text_from_context(self) -> str:
        if self.context.current_text and self.context.current_text.strip():
            return self.context.current_text.strip()
        conversation = self.context.conversation_context
        if conversation is not None:
            current = getattr(getattr(conversation, "current_message", None), "content", None)
            if isinstance(current, str) and current.strip():
                return current.strip()
        for message in reversed(self.context.provider_messages):
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return ""

    def _semantic_retrieval(
        self,
        query: str,
        *,
        seed_id: str | None = None,
        desired_view: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        semantic = self.context.semantic_search_service
        if semantic is None or not query.strip():
            return {
                "status": "skipped",
                "reason": "semantic_search_service_missing" if semantic is None else "empty_query",
                "desired_view": desired_view,
            }
        try:
            # Search services are application-singletons. Copy before injecting the
            # request owner so concurrent users cannot observe each other's owner
            # scoped profile-memory visibility.
            if self.context.graph_owner_id and hasattr(semantic, "owner_graph_node_id"):
                semantic = copy(semantic)
                semantic.owner_graph_node_id = self.context.graph_owner_id
            kwargs = {"limit": limit}
            if seed_id:
                kwargs["target_ids"] = [seed_id]
            if hasattr(semantic, "search_hybrid"):
                result = semantic.search_hybrid(query, **kwargs)
            elif hasattr(semantic, "search_semantic"):
                result = semantic.search_semantic(query, **kwargs)
            else:
                result = semantic.search(query=query, **kwargs)
            return {"status": "ok", "desired_view": desired_view, "result": _serialize(result)}
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "semantic_retrieval_failed",
                "message": str(exc),
                "exception_type": exc.__class__.__name__,
                "desired_view": desired_view,
            }

    def _memory_plan_action(
        self,
        action_id: str,
        *,
        metadata: dict[str, Any],
    ) -> MemoryPlanAction | ToolResult:
        candidates: list[Any] = []
        current_payload = self.context.current_payload
        if current_payload is not None:
            payload_metadata = getattr(current_payload, "metadata", {}) or {}
            plan = payload_metadata.get("memory_plan") or payload_metadata.get("plan")
            if isinstance(plan, dict):
                candidates.extend(plan.get("actions") or [])
            candidates.extend(payload_metadata.get("plan_actions") or [])
        if metadata.get("action"):
            candidates.append(metadata["action"])
        for candidate in candidates:
            try:
                action = MemoryPlanAction.model_validate(candidate)
            except Exception:
                continue
            if action.action_id == action_id:
                return action
        return _update_tool_error(
            "run_memory_creation",
            "memory_plan_action_not_found",
            f"Memory creation action '{action_id}' was not found in the active ingestion context.",
            "Retry with an action_id from the current MemoryPlan or include metadata.action.",
            retryable=True,
            details={"action_id": action_id},
        )

    def _handle_ask_clarification(
        self,
        doubts: list[dict[str, Any]],
    ) -> ToolResult:
        runtime = self.context.agentic_runtime
        if runtime is None:
            return _missing_dependency("ask_clarification", "agentic_runtime")
        try:
            if self.context.ref_context is None:
                return _update_tool_error(
                    "ask_clarification",
                    "missing_reference_context",
                    "The active canonical reference context is not available.",
                    "Retry from a run that carries its canonical reference context.",
                    retryable=False,
                )
            invalid_refs = _invalid_handoff_refs(
                doubts,
                ref_context=self.context.ref_context,
            )
            if invalid_refs:
                return _update_tool_error(
                    "ask_clarification",
                    "invalid_clarification_reference",
                    "Clarification doubts contain refs that are not available in the current run.",
                    "Use only model-facing refs supplied in the current context.",
                    retryable=True,
                    details={"invalid_refs": invalid_refs},
                )
            conversation = self._conversation_context()
            handoff = ClarificationHandoffRequest(
                doubts=doubts,
                invoker_state_id=self.context.state_id or "unknown",
                invoker_tool_call_id=self.context.current_tool_call_id,
                parent_frame_id=self.context.frame_id,
            )
            session_input = ClarificationSessionInput(
                handoff=handoff,
                conversation=conversation,
                master_history=_master_history_messages(conversation),
                context_payload=_serialize(self.context.current_payload) or {},
                session_id=self.context.session_id or conversation.context_id,
                parent_frame_id=self.context.frame_id,
                parent_tool_call_id=self.context.current_tool_call_id,
            )
            log_event(
                logger,
                "clarification.handoff.created",
                component="agentic_tools",
                session_id=self.context.session_id,
                frame_id=self.context.frame_id,
                state_id=self.context.state_id,
                doubt_count=len(doubts),
            )
            return runtime.run_child_frame(
                parent_execution_context=self.context,
                conversation_context=conversation,
                child_state=AgenticStateId.CLARIFICATION_AGENT,
                child_payload=session_input,
                tool_name="ask_clarification",
                continuation_required=True,
            )
        except Exception as exc:
            return _tool_error(
                "ask_clarification",
                "invalid_clarification_handoff",
                f"Clarification handoff failed validation: {exc}",
                (
                    "Pass detailed doubts with stable refs, missing information, "
                    "and the reason each doubt matters."
                ),
                retryable=True,
                details={"exception_type": exc.__class__.__name__},
            )

    def _handle_lookup_candidates(
        self,
        candidate_ref: str,
        entity_type: str,
        display_name: str | None = None,
        aliases: list[str] | None = None,
        typed_identity_values: Any | None = None,
        max_candidates: int = 5,
    ) -> ToolResult:
        if isinstance(typed_identity_values, list):
            typed_identity_values = {
                str(item.get("key")): list(item.get("values") or [])
                for item in typed_identity_values
                if isinstance(item, dict) and item.get("key")
            }
        result = self._clarification_tools().lookup_candidates(
            candidate_ref=candidate_ref,
            entity_type=entity_type,
            display_name=display_name,
            aliases=aliases,
            typed_identity_values=typed_identity_values,
            max_candidates=max_candidates,
        )
        self._sync_ref_context()
        return result

    def _handle_get_candidate_context(
        self,
        refs: list[str],
        include_relationships: bool = True,
        include_evidence: bool = True,
        limit: int = 5,
    ) -> ToolResult:
        result = self._clarification_tools().get_candidate_context(
            refs=refs,
            include_relationships=include_relationships,
            include_evidence=include_evidence,
            limit=limit,
        )
        self._sync_ref_context()
        return result

    def _handle_get_relationship_context(
        self,
        from_ref: str,
        to_ref: str,
        relationship_type: str | None = None,
        limit: int = 5,
    ) -> ToolResult:
        result = self._clarification_tools().get_relationship_context(
            from_ref=from_ref,
            to_ref=to_ref,
            relationship_type=relationship_type,
            limit=limit,
        )
        self._sync_ref_context()
        return result

    def _handle_pick_one(self, **kwargs: Any) -> ToolResult:
        return self._question_tool("pick_one", kwargs)

    def _handle_pick_many(self, **kwargs: Any) -> ToolResult:
        return self._question_tool("pick_many", kwargs)

    def _handle_confirm(self, **kwargs: Any) -> ToolResult:
        return self._question_tool("confirm", kwargs)

    def _handle_ask_text(self, **kwargs: Any) -> ToolResult:
        return self._question_tool("ask_text", kwargs)

    def _handle_ask_text_or_audio(self, **kwargs: Any) -> ToolResult:
        return self._question_tool("ask_text_or_audio", kwargs)

    def _question_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        return self._clarification_tools().build_question(
            tool_name=tool_name,
            request=arguments,
            frame_id=self.context.frame_id or self.context.session_id or "session-local",
            tool_call_id=self.context.current_tool_call_id,
            origin_state_id=self.context.state_id or "clarification_agent",
        )

    def _clarification_tools(self) -> ClarificationToolService:
        ref_context = self.context.ref_context
        if ref_context is None:
            raise ValueError("The active canonical reference context is not configured.")
        return ClarificationToolService(
            graph_service=self.context.graph_service,
            ref_context=ref_context,
            owner_manager=self.context.metadata.get("owner_manager"),
            owner_graph_node_id=self.context.graph_owner_id,
        )

    def _sync_ref_context(self) -> None:
        """Keep the canonical context available to durable child frames."""

        if self.context.ref_context is not None:
            self.context.metadata["ref_context_snapshot"] = self.context.ref_context.snapshot()

    def _handle_get_context_package(
        self,
        node_id: str,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> ToolResult:
        return self._graph_call(
            "get_context_package",
            lambda graph: graph.get_context_package(
                node_id,
                include_history=include_history,
                timeline_limit=timeline_limit,
                relationship_limit=relationship_limit,
            ),
        )

    def _handle_get_entity_detail(
        self,
        node_id: str,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> ToolResult:
        return self._graph_call(
            "get_entity_detail",
            lambda graph: graph.get_entity_detail(
                node_id,
                include_history=include_history,
                include_archived=include_archived,
                limit=limit,
            ),
        )

    def _handle_get_memories_involving_node(
        self,
        node_id: str,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> ToolResult:
        return self._graph_call(
            "get_memories_involving_node",
            lambda graph: graph.get_memories_for_node(
                node_id,
                include_history=include_history,
                include_archived=include_archived,
                limit=limit,
            ),
        )

    def _handle_get_timeline(
        self,
        node_id: str,
        from_time: str | None = None,
        to_time: str | None = None,
        include_history: bool = False,
        limit: int = 100,
    ) -> ToolResult:
        return self._graph_call(
            "get_timeline",
            lambda graph: graph.get_timeline_for_node(
                node_id,
                from_time=from_time,
                to_time=to_time,
                include_history=include_history,
                limit=limit,
            ),
        )

    def _handle_get_neighborhood_view(
        self,
        seed_id: str,
        depth: int = 1,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 100,
    ) -> ToolResult:
        return self._graph_call(
            "get_neighborhood_view",
            lambda graph: graph.get_neighborhood_view(
                seed_id=seed_id,
                depth=depth,
                include_history=include_history,
                include_archived=include_archived,
                limit=limit,
            ),
        )

    def _handle_get_map_view(
        self,
        seed_id: str | None = None,
        city: str | None = None,
        country: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
    ) -> ToolResult:
        return self._graph_call(
            "get_map_view",
            lambda graph: graph.get_map_view(
                seed_id=seed_id,
                city=city,
                country=country,
                from_time=from_time,
                to_time=to_time,
                limit=limit,
            ),
        )

    def _handle_get_target_evidence(self, target_id: str, limit: int = 50) -> ToolResult:
        return self._graph_call(
            "get_target_evidence",
            lambda graph: graph.get_source_evidence(target_id, limit=limit),
        )

    def _handle_get_latest_contact_details(self, node_id: str, limit: int = 20) -> ToolResult:
        def call(graph):
            view = graph.get_neighborhood_view(
                seed_id=node_id,
                depth=1,
                include_history=False,
                include_archived=False,
                limit=limit,
            )
            payload = _serialize(view)
            contacts = [
                node for node in payload.get("nodes", []) if node.get("label") == "ContactPoint"
            ]
            return {"node_id": node_id, "contacts": contacts}

        return self._graph_call("get_latest_contact_details", call)

    def _handle_get_change_records(
        self,
        target_id: str,
        target_kind: str | None = None,
        limit: int = 50,
    ) -> ToolResult:
        return self._graph_call(
            "get_change_records",
            lambda graph: graph.get_change_records_for_target(
                target_id,
                target_kind=target_kind,
                limit=limit,
            ),
        )

    def _handle_get_relationship_state_history(
        self,
        context_id: str,
        limit: int = 50,
    ) -> ToolResult:
        return self._graph_call(
            "get_relationship_state_history",
            lambda graph: graph.get_relationship_states(context_id, limit=limit),
        )

    def _handle_resolve_graph_update_targets(
        self,
        query: str,
        target_ids: list[str] | None = None,
        limit: int = 5,
    ) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _update_tool_error(
                "resolve_graph_update_targets",
                "missing_dependency",
                "Graph service is not configured.",
                "Graph update cannot continue without graph_service.",
                retryable=False,
            )
        try:
            resolved_target_ids, error = self._resolve_refs(
                target_ids or [],
                expected_kind=RefObjectKind.NODE,
                tool_name="resolve_graph_update_targets",
            )
            if error is not None:
                return error
            explicit_targets = [graph.get_node(target_id) for target_id in resolved_target_ids]
            if explicit_targets:
                return _update_tool_result(
                    "resolve_graph_update_targets",
                    summary="Explicit graph update targets resolved.",
                    updated_refs=[],
                    affected_graph_ids=[
                        str(target.properties["id"]) for target in explicit_targets
                    ],
                    data={
                        "targets": _serialize(explicit_targets),
                        "requires_clarification": False,
                    },
                )

            semantic = self.context.semantic_search_service
            candidates: list[Any] = []
            if semantic is not None:
                try:
                    if hasattr(semantic, "search_semantic"):
                        result = semantic.search_semantic(query, limit=limit)
                    else:
                        result = semantic.search(query=query, limit=limit)
                    for hit in getattr(result, "hits", [])[:limit]:
                        target_id = getattr(hit, "display_target_id", None) or getattr(
                            hit,
                            "target_id",
                            None,
                        )
                        if target_id:
                            candidates.append(graph.get_node(str(target_id)))
                except Exception:
                    candidates = []
            if not candidates:
                candidates = graph.search_nodes(query=query, limit=limit)
            candidate_ids = [
                str(candidate.properties["id"])
                for candidate in candidates
                if getattr(candidate, "properties", None)
            ]
            return _update_tool_result(
                "resolve_graph_update_targets",
                summary="Graph update target candidates retrieved.",
                affected_graph_ids=candidate_ids,
                data={
                    "candidates": _serialize(candidates),
                    "requires_clarification": len(candidate_ids) != 1,
                },
                suggested_next_action=(
                    "Use the resolved target id in write tools, or ask clarification if ambiguous."
                ),
            )
        except Exception as exc:
            return _update_exception_result("resolve_graph_update_targets", exc)

    def _resolve_ref(
        self,
        value: str,
        *,
        expected_kind: RefObjectKind,
        tool_name: str,
    ) -> tuple[str | None, ToolResult | None]:
        normalized = str(value or "").strip()
        ref_context = self.context.ref_context
        if ref_context is None:
            return normalized, None
        try:
            return ref_context.resolve(normalized, expected_kind=expected_kind), None
        except ValueError as exc:
            return None, _update_tool_error(
                tool_name,
                "invalid_model_reference",
                str(exc),
                "Use a supplied readable ref from the active context.",
                retryable=True,
                details={"ref": normalized, "expected_kind": expected_kind.value},
            )

    def _resolve_refs(
        self,
        values: list[str],
        *,
        expected_kind: RefObjectKind,
        tool_name: str,
    ) -> tuple[list[str], ToolResult | None]:
        resolved: list[str] = []
        for value in values:
            if not value:
                continue
            backend_id, error = self._resolve_ref(
                value,
                expected_kind=expected_kind,
                tool_name=tool_name,
            )
            if error is not None:
                return [], error
            if backend_id:
                resolved.append(backend_id)
        return resolved, None

    def _handle_create_memory_log(
        self,
        title: str,
        log_text: str,
        host_target_ids: list[str],
        primary_host_target_id: str | None = None,
        involved_target_ids: list[str] | None = None,
        relationship_context_target_ids: list[str] | None = None,
        media_refs: list[str] | None = None,
        log_kind: str | None = None,
        source_kind: str | None = None,
        happened_at: str | None = None,
    ) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _update_tool_error(
                "create_memory_log",
                "missing_dependency",
                "Graph service is not configured.",
                "Graph update cannot continue without graph_service.",
                retryable=False,
            )
        host_ids, error = self._resolve_refs(
            host_target_ids,
            expected_kind=RefObjectKind.NODE,
            tool_name="create_memory_log",
        )
        if error is not None:
            return error
        if not host_ids:
            return _update_tool_error(
                "create_memory_log",
                "missing_host_target",
                "MemoryLog creation requires at least one host target.",
                "Resolve a target node first, then call create_memory_log with host_target_ids.",
                retryable=True,
                details={"host_target_ids": host_target_ids},
            )
        if len(host_ids) > 1 and not primary_host_target_id:
            return _update_tool_error(
                "create_memory_log",
                "missing_primary_host",
                "MemoryLog with multiple hosts requires primary_host_target_id.",
                "Select the main host target and retry.",
                retryable=True,
                details={"host_target_ids": host_ids},
            )
        primary_host_input = primary_host_target_id or host_target_ids[0]
        primary_host, error = self._resolve_ref(
            primary_host_input,
            expected_kind=RefObjectKind.NODE,
            tool_name="create_memory_log",
        )
        if error is not None:
            return error
        if primary_host not in host_ids:
            return _update_tool_error(
                "create_memory_log",
                "invalid_primary_host",
                "primary_host_target_id must be one of host_target_ids.",
                "Retry with a primary_host_target_id included in host_target_ids.",
                retryable=True,
                details={"primary_host_target_id": primary_host, "host_target_ids": host_ids},
            )
        try:
            involved_ids, error = self._resolve_refs(
                involved_target_ids or [],
                expected_kind=RefObjectKind.NODE,
                tool_name="create_memory_log",
            )
            if error is not None:
                return error
            context_ids, error = self._resolve_refs(
                relationship_context_target_ids or [],
                expected_kind=RefObjectKind.CONTEXT,
                tool_name="create_memory_log",
            )
            if error is not None:
                return error
            primary_node = graph.get_node(primary_host)
            for target_id in [
                *host_ids,
                *involved_ids,
                *context_ids,
            ]:
                graph.get_node(str(target_id))
            properties = {
                "title": title,
                "log_text": log_text,
                "log_kind": log_kind,
                "source_kind": source_kind or "graph_update",
                "happened_at": happened_at,
                "primary_host_target_id": primary_host,
                "primary_host_target_label": primary_node.label,
                "host_target_ids": host_ids,
                "involved_target_ids": involved_ids,
                "relationship_context_target_ids": context_ids,
                "media_refs": list(media_refs or []),
            }
            log = graph.upsert_node("MemoryLog", _drop_none(properties))
            log_id = str(log.properties["id"])
            for host_id in host_ids:
                graph.upsert_relationship(
                    "HAS_MEMORY_LOG",
                    host_id,
                    log_id,
                    {"primary": host_id == primary_host, "role": "host"},
                )
            for involved_id in involved_ids:
                graph.upsert_relationship("INVOLVES", log_id, str(involved_id), {})
            for context_id in context_ids:
                graph.upsert_relationship(
                    "UPDATES_RELATIONSHIP",
                    log_id,
                    str(context_id),
                    {},
                )
            refreshed = self._refresh_vectors(
                "create_memory_log",
                [
                    log_id,
                    *host_ids,
                    *involved_ids,
                    *context_ids,
                ],
            )
            created_ref = self._bind_created_ref(
                log_id,
                expected_kind=RefObjectKind.MEMORY,
                label="MemoryLog",
            )
            return _update_tool_result(
                "create_memory_log",
                summary="MemoryLog created and linked.",
                created_refs=[created_ref or log_id],
                affected_graph_ids=[
                    *self._refs_for_backend_ids(
                        [log_id, *host_ids, *involved_ids, *context_ids],
                    ),
                ],
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"memory_log": self._model_facing_value(log)},
            )
        except Exception as exc:
            return _update_exception_result("create_memory_log", exc)

    def _handle_create_graph_node(self, label: str, properties_json: str) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _update_tool_error(
                "create_graph_node",
                "missing_dependency",
                "Graph service is not configured.",
                "Graph update cannot continue without graph_service.",
                retryable=False,
            )
        if label not in GRAPH_UPDATE_CREATABLE_LABELS:
            return _update_tool_error(
                "create_graph_node",
                "graph_update_label_not_allowed",
                f"Graph update tools cannot create label '{label}' in Wave 5 v1.",
                "Use a supported non-destructive label or defer merge/destructive work.",
                retryable=False,
                details={"label": label},
            )
        properties = _parse_json_object("create_graph_node", properties_json)
        if isinstance(properties, ToolResult):
            return properties
        lifecycle_state = properties.get("lifecycle_state")
        if lifecycle_state in {"archived", "deleted"}:
            return _update_tool_error(
                "create_graph_node",
                "destructive_lifecycle_not_allowed",
                "Wave 5 graph update tools do not allow archive/delete lifecycle states.",
                "Create active/non-destructive graph records only.",
                retryable=False,
                details={"lifecycle_state": lifecycle_state},
            )
        try:
            node = graph.upsert_node(label, properties)
            node_id = str(node.properties["id"])
            created_ref = self._bind_created_ref(
                node_id,
                expected_kind=RefObjectKind.NODE,
                label=label,
            )
            refreshed = self._refresh_vectors("create_graph_node", [node_id])
            return _update_tool_result(
                "create_graph_node",
                summary=f"{label} node created.",
                created_refs=[created_ref or node_id],
                affected_graph_ids=self._refs_for_backend_ids([node_id]),
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"node": self._model_facing_value(node)},
            )
        except Exception as exc:
            return _update_exception_result("create_graph_node", exc)

    def _handle_patch_graph_node(self, node_id: str, properties_json: str) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _update_tool_error(
                "patch_graph_node",
                "missing_dependency",
                "Graph service is not configured.",
                "Graph update cannot continue without graph_service.",
                retryable=False,
            )
        properties = _parse_json_object("patch_graph_node", properties_json)
        if isinstance(properties, ToolResult):
            return properties
        lifecycle_state = properties.get("lifecycle_state")
        if lifecycle_state in {"archived", "deleted"}:
            return _update_tool_error(
                "patch_graph_node",
                "destructive_lifecycle_not_allowed",
                "Wave 5 graph update tools do not allow archive/delete lifecycle transitions.",
                "Use a non-destructive patch or defer deletion/merge work.",
                retryable=False,
                details={"lifecycle_state": lifecycle_state},
            )
        resolved_node_id, error = self._resolve_ref(
            node_id,
            expected_kind=RefObjectKind.NODE,
            tool_name="patch_graph_node",
        )
        if error is not None:
            return error
        try:
            node = graph.patch_node(resolved_node_id, properties)
            refreshed = self._refresh_vectors("patch_graph_node", [resolved_node_id])
            return _update_tool_result(
                "patch_graph_node",
                summary="Graph node patched.",
                updated_refs=self._refs_for_backend_ids([resolved_node_id]),
                affected_graph_ids=self._refs_for_backend_ids([resolved_node_id]),
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"node": self._model_facing_value(node)},
            )
        except Exception as exc:
            return _update_exception_result("patch_graph_node", exc)

    def _handle_upsert_graph_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties_json: str,
    ) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _update_tool_error(
                "upsert_graph_relationship",
                "missing_dependency",
                "Graph service is not configured.",
                "Graph update cannot continue without graph_service.",
                retryable=False,
            )
        if relationship_type in GRAPH_UPDATE_BLOCKED_RELATIONSHIP_TYPES:
            return _update_tool_error(
                "upsert_graph_relationship",
                "graph_update_relationship_type_not_allowed",
                f"Graph update tools cannot upsert relationship type '{relationship_type}' in Wave 5 v1.",
                "Use a supported non-destructive relationship type or defer merge/destructive work.",
                retryable=False,
                details={"relationship_type": relationship_type},
            )
        properties = _parse_json_object("upsert_graph_relationship", properties_json)
        if isinstance(properties, ToolResult):
            return properties
        lifecycle_state = properties.get("lifecycle_state")
        if lifecycle_state in {"archived", "deleted"}:
            return _update_tool_error(
                "upsert_graph_relationship",
                "destructive_lifecycle_not_allowed",
                "Wave 5 graph update tools do not allow archive/delete lifecycle transitions.",
                "Use a non-destructive relationship update or defer deletion/merge work.",
                retryable=False,
                details={"lifecycle_state": lifecycle_state},
            )
        resolved_from_id, error = self._resolve_ref(
            from_id,
            expected_kind=RefObjectKind.NODE,
            tool_name="upsert_graph_relationship",
        )
        if error is not None:
            return error
        resolved_to_id, error = self._resolve_ref(
            to_id,
            expected_kind=RefObjectKind.NODE,
            tool_name="upsert_graph_relationship",
        )
        if error is not None:
            return error
        try:
            relationship = graph.upsert_relationship(
                relationship_type,
                resolved_from_id,
                resolved_to_id,
                properties,
            )
            relationship_id = str(relationship.properties["id"])
            created_ref = self._bind_created_ref(
                relationship_id,
                expected_kind=RefObjectKind.EDGE,
                label="Relationship",
            )
            refreshed = self._refresh_vectors(
                "upsert_graph_relationship",
                [resolved_from_id, resolved_to_id],
            )
            return _update_tool_result(
                "upsert_graph_relationship",
                summary="Graph relationship upserted.",
                created_refs=[created_ref or relationship_id],
                affected_graph_ids=self._refs_for_backend_ids(
                    [resolved_from_id, resolved_to_id],
                ),
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"relationship": self._model_facing_value(relationship)},
            )
        except Exception as exc:
            return _update_exception_result("upsert_graph_relationship", exc)

    def _handle_create_relationship_state(
        self,
        context_id: str,
        properties_json: str,
        make_current: bool = True,
    ) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _update_tool_error(
                "create_relationship_state",
                "missing_dependency",
                "Graph service is not configured.",
                "Graph update cannot continue without graph_service.",
                retryable=False,
            )
        properties = _parse_json_object("create_relationship_state", properties_json)
        if isinstance(properties, ToolResult):
            return properties
        resolved_context_id, error = self._resolve_ref(
            context_id,
            expected_kind=RefObjectKind.CONTEXT,
            tool_name="create_relationship_state",
        )
        if error is not None:
            return error
        try:
            state = graph.create_relationship_state(
                resolved_context_id,
                properties,
                make_current=make_current,
            )
            state_id = str(state.properties["id"])
            refreshed = self._refresh_vectors(
                "create_relationship_state",
                [resolved_context_id, state_id],
            )
            return _update_tool_result(
                "create_relationship_state",
                summary="RelationshipState created.",
                created_refs=[
                    self._bind_created_ref(
                        state_id,
                        expected_kind=RefObjectKind.CONTEXT,
                        label="RelationshipState",
                    )
                    or state_id
                ],
                updated_refs=(
                    self._refs_for_backend_ids([resolved_context_id])
                    if make_current
                    else []
                ),
                affected_graph_ids=self._refs_for_backend_ids(
                    [resolved_context_id, state_id],
                ),
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"relationship_state": self._model_facing_value(state)},
            )
        except Exception as exc:
            return _update_exception_result("create_relationship_state", exc)

    def _bind_created_ref(
        self,
        backend_id: str,
        *,
        expected_kind: RefObjectKind,
        label: str,
    ) -> str | None:
        ref_context = self.context.ref_context
        if ref_context is None:
            return None
        payload = self.context.current_payload
        action = getattr(payload, "action", None)
        action_refs = list(getattr(action, "target_refs", []) or [])
        for ref in action_refs:
            entry = ref_context.entries.get(ref)
            if entry is None or entry.object_kind != expected_kind or entry.backend_id:
                continue
            ref_context.resolve_backend_id(ref, backend_id, status="created")
            return ref
        return ref_context.register_existing(
            backend_id,
            expected_kind,
            label=label,
            source="graph_write",
        )

    def _refs_for_backend_ids(self, backend_ids: list[str]) -> list[str]:
        ref_context = self.context.ref_context
        if ref_context is None:
            return [str(item) for item in backend_ids]
        return [
            ref_context.ref_for_backend_id(str(item)) or str(item)
            for item in backend_ids
        ]

    def _model_facing_value(self, value: Any) -> Any:
        return _model_facing_retrieval_value(_serialize(value), self.context.ref_context)

    def _refresh_vectors(self, tool_name: str, target_ids: list[str]) -> dict[str, Any]:
        service = self.context.vectorization_service or getattr(
            self.context.ingestion_service, "vectorization_service", None
        )
        if service is None:
            return {
                "refreshed_vector_scopes": [],
                "diagnostics": [
                    {
                        "level": "warning",
                        "code": "vectorization_service_missing",
                        "message": "Vector refresh skipped because no vectorization service is configured.",
                    }
                ],
            }
        try:
            result = service.vectorize_targets(target_ids, source_id=tool_name)
            payload = _serialize(result)
            scopes = payload.get("collections") or payload.get("refreshed_vector_scopes")
            if not scopes and payload.get("collection"):
                scopes = [payload["collection"]]
            return {
                "refreshed_vector_scopes": scopes or [],
                "diagnostics": [
                    {"level": "info", "code": "vector_refresh_done", "result": payload}
                ],
            }
        except Exception as exc:
            return {
                "refreshed_vector_scopes": [],
                "diagnostics": [
                    {
                        "level": "error",
                        "code": "vector_refresh_failed",
                        "message": str(exc),
                        "exception_type": exc.__class__.__name__,
                    }
                ],
            }

    def _graph_call(self, name: str, callback) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _missing_dependency(name, "graph_service")
        try:
            result = callback(graph)
        except Exception as exc:
            return _exception_result(name, exc)
        return ToolResult(
            status="ok",
            output=f"{name} completed.",
            data={"operation": name, "result": _serialize(result)},
        )


def _graph_context_from_retrieval(
    retrieval: dict[str, Any],
    *,
    ref_context: RefContext | None = None,
) -> GraphContextPackage | None:
    if retrieval.get("status") != "ok":
        return None
    result = retrieval.get("result")
    if not isinstance(result, dict):
        return None
    packages = result.get("context_packages") or []
    aliases: dict[str, str] = {}
    candidate_matches: list[dict[str, Any]] = []
    for index, package in enumerate(packages[:5], start=1):
        if isinstance(package, dict):
            target = package.get("target")
            target_id = (
                target.get("id")
                if isinstance(target, dict)
                else package.get("target_id") or package.get("seed_id")
            )
            target_ref = _register_retrieval_object(target, ref_context)
            if target_ref is None and target_id and ref_context is not None:
                target_ref = _register_retrieval_object(
                    {"id": target_id, "label": package.get("target_label") or "Node"},
                    ref_context,
                )
            if target_ref:
                aliases[f"retrieval_{index}"] = target_ref
            for item in [
                *(package.get("current_facts") or []),
                *(package.get("relationships") or []),
                *(package.get("relationship_contexts") or []),
                *(package.get("evidence") or []),
                *(package.get("matched_records") or []),
            ]:
                _register_retrieval_object(item, ref_context)
            candidate_matches.append(_model_facing_retrieval_value(package, ref_context))
    hits = result.get("hits") or []
    for hit in hits[:10]:
        if isinstance(hit, dict):
            _register_retrieval_object(hit.get("target"), ref_context)
            candidate_matches.append(_model_facing_retrieval_value(hit, ref_context))
    if not aliases and not candidate_matches:
        return None
    return GraphContextPackage(
        aliases=aliases,
        candidate_matches=candidate_matches,
        ref_context=ref_context,
        metadata={"source": "scoped_retrieval"},
        owner_snapshot=_owner_snapshot_from_retrieval(retrieval),
    )


def _owner_snapshot_from_retrieval(retrieval: dict[str, Any]) -> OwnerSnapshot | None:
    raw = retrieval.get("owner_snapshot")
    if isinstance(raw, dict):
        return OwnerSnapshot.model_validate(raw)
    return None


def _invalid_handoff_refs(
    doubts: list[dict[str, Any]],
    *,
    ref_context: RefContext,
) -> list[str]:
    """Validate handoff refs against the active canonical context."""

    allowed = {
        str(ref)
        for ref in ref_context.entries
    }
    referenced = {
        str(ref)
        for doubt in doubts
        if isinstance(doubt, dict)
        for ref in [*(doubt.get("refs") or []), *(doubt.get("evidence_refs") or [])]
        if ref
    }
    return sorted(referenced - allowed)


def _ref_context_from_retrieval(
    retrieval: dict[str, Any],
    *,
    session_id: str | None,
) -> RefContext:
    context = RefContext(session_id=session_id)
    result = retrieval.get("result")
    if not isinstance(result, dict):
        return context
    for package in list(result.get("context_packages") or [])[:5]:
        if not isinstance(package, dict):
            continue
        _register_retrieval_object(package.get("target"), context)
        for item in [
            *(package.get("current_facts") or []),
            *(package.get("relationships") or []),
            *(package.get("relationship_contexts") or []),
            *(package.get("evidence") or []),
            *(package.get("matched_records") or []),
        ]:
            _register_retrieval_object(item, context)
    for hit in list(result.get("hits") or [])[:10]:
        if isinstance(hit, dict):
            _register_retrieval_object(hit.get("target"), context)
            _register_retrieval_object(hit.get("canonical_target"), context)
            for item in hit.get("matched_records") or []:
                _register_retrieval_object(item, context)
    return context


def _ensure_owner_ref(
    ref_context: RefContext,
    graph_owner_id: str,
    owner_snapshot: OwnerSnapshot | None,
) -> None:
    ref_context.bind_owner(
        graph_owner_id,
        name=(owner_snapshot.display_name if owner_snapshot is not None else None),
    )


def _register_retrieval_object(value: Any, context: RefContext | None) -> str | None:
    if context is None or not isinstance(value, dict):
        return None
    backend_id = value.get("id") or value.get("backend_id")
    if not backend_id:
        return None
    if value.get("from_id") is not None and value.get("to_id") is not None:
        kind = RefObjectKind.EDGE
        for endpoint_key in ("from_id", "to_id"):
            endpoint_id = value.get(endpoint_key)
            if endpoint_id and context.ref_for_backend_id(str(endpoint_id)) is None:
                context.register_existing(
                    str(endpoint_id),
                    RefObjectKind.NODE,
                    label="Node",
                    source="semantic_retrieval_endpoint",
                )
    else:
        label = str(value.get("label") or value.get("type") or "")
        kind = (
            RefObjectKind.MEMORY
            if label == "MemoryLog"
            else RefObjectKind.MEDIA
            if label == "MediaAsset"
            else RefObjectKind.CONTEXT
            if label in {
                "Claim",
                "Perception",
                "RelationshipContext",
                "RelationshipState",
                "ProfileMemory",
            }
            else RefObjectKind.NODE
        )
    try:
        return context.register_existing(
            str(backend_id),
            kind,
            label=str(value.get("label") or "Node"),
            type=str(value.get("type")) if value.get("type") else None,
            name=_retrieval_display_name(value),
            summary=_retrieval_summary(value),
            aliases=[str(item) for item in value.get("aliases", []) if item],
            source="semantic_retrieval",
        )
    except ValueError:
        return context.ref_for_backend_id(str(backend_id))


def _model_facing_retrieval_value(value: Any, context: RefContext | None) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"alias_map", "id", "backend_id", "node_id", "package_id", "vector_id"}:
                continue
            if key.endswith("_id"):
                ref = context.ref_for_backend_id(str(item)) if context and item else None
                if ref:
                    result[key.removesuffix("_id") + "_ref"] = ref
                continue
            if key.endswith("_ids"):
                refs = [
                    context.ref_for_backend_id(str(item_id))
                    for item_id in (item or [])
                    if context and context.ref_for_backend_id(str(item_id))
                ]
                if refs:
                    result[key.removesuffix("_ids") + "_refs"] = refs
                continue
            result[key] = _model_facing_retrieval_value(item, context)
        return result
    if isinstance(value, list):
        return [_model_facing_retrieval_value(item, context) for item in value]
    return value


def _retrieval_display_name(value: dict[str, Any]) -> str | None:
    for key in ("display_name", "name", "title", "label_text", "description"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _retrieval_summary(value: dict[str, Any]) -> str | None:
    for key in ("summary", "description", "log_text", "text", "document_preview"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _update_tool_result(
    tool_name: str,
    *,
    summary: str,
    created_refs: list[str] | None = None,
    updated_refs: list[str] | None = None,
    affected_graph_ids: list[str] | None = None,
    refreshed_vector_scopes: list[str] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
    suggested_next_action: str | None = None,
    data: dict[str, Any] | None = None,
) -> ToolResult:
    payload = {
        "operation": tool_name,
        "summary": summary,
        "created_refs": _dedupe_strings(created_refs or []),
        "updated_refs": _dedupe_strings(updated_refs or []),
        "affected_graph_ids": _dedupe_strings(affected_graph_ids or []),
        "refreshed_vector_scopes": _dedupe_strings(refreshed_vector_scopes or []),
        "diagnostics": diagnostics or [],
        "suggested_next_action": suggested_next_action,
    }
    if data:
        payload.update(data)
    return ToolResult(status="ok", output=summary, data=payload)


def _update_tool_error(
    tool_name: str,
    code: str,
    message: str,
    hint: str,
    *,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    payload = {
        "operation": tool_name,
        "summary": message,
        "created_refs": [],
        "updated_refs": [],
        "affected_graph_ids": [],
        "refreshed_vector_scopes": [],
        "diagnostics": [
            {
                "level": "warning" if retryable else "error",
                "code": code,
                "message": message,
                "hint": hint,
                "retryable": retryable,
                "details": details or {},
            }
        ],
        "suggested_next_action": hint,
        "error_code": code,
        "retryable": retryable,
        "validation_details": details or {},
    }
    return ToolResult(
        status="recoverable_error" if retryable else "blocked",
        output=message,
        data=payload,
        error=ToolError(
            message=message,
            code=code,
            hint=hint,
            retryable=retryable,
            details={"tool": tool_name, **(details or {})},
        ),
    )


def _update_exception_result(tool_name: str, exc: Exception) -> ToolResult:
    exc_type = exc.__class__.__name__
    retryable = exc_type in {"GraphValidationError", "ValidationError", "ValueError"}
    return _update_tool_error(
        tool_name,
        "validation_failed" if retryable else "backend_execution_failed",
        str(exc),
        (
            "Inspect the validation details and retry with corrected arguments."
            if retryable
            else "The backend failed while executing this tool; avoid retrying unchanged arguments."
        ),
        retryable=retryable,
        details={"exception_type": exc_type},
    )


def _parse_json_object(tool_name: str, value: str) -> dict[str, Any] | ToolResult:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        return _update_tool_error(
            tool_name,
            "invalid_json",
            f"properties_json must be a JSON object: {exc}",
            "Retry with a valid JSON object string.",
            retryable=True,
            details={"json_error": str(exc)},
        )
    if not isinstance(parsed, dict):
        return _update_tool_error(
            tool_name,
            "invalid_json_object",
            "properties_json must decode to an object.",
            'Retry with a JSON object, for example {"status":"active"}.',
            retryable=True,
            details={"decoded_type": type(parsed).__name__},
        )
    return parsed


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


def _master_history_messages(conversation: Any) -> list[dict[str, str]]:
    metadata = getattr(conversation, "metadata", {}) or {}
    persisted_history = metadata.get("master_llm_history")
    if isinstance(persisted_history, list):
        return [
            {
                "role": str(item["role"]),
                "content": str(item["content"]),
            }
            for item in persisted_history
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and item.get("content")
        ]
    messages: list[dict[str, str]] = []
    for message in [
        *(getattr(conversation, "history", []) or []),
        getattr(conversation, "current_message", None),
    ]:
        if message is None:
            continue
        content = str(getattr(message, "content", "") or "").strip()
        kind = str(getattr(getattr(message, "kind", None), "value", getattr(message, "kind", "")))
        role = "user" if kind == "user" else "assistant" if kind == "assistant" else ""
        if content and role:
            messages.append({"role": role, "content": content})
    return messages


def _missing_dependency(tool_name: str, dependency: str) -> ToolResult:
    return _tool_error(
        tool_name,
        "missing_dependency",
        f"Tool '{tool_name}' cannot run because '{dependency}' is not configured.",
        f"Configure AgenticToolExecutionContext.{dependency} or choose a tool that does not need it.",
        retryable=False,
        details={"missing_dependency": dependency},
    )


def _exception_result(tool_name: str, exc: Exception) -> ToolResult:
    return _tool_error(
        tool_name,
        "tool_backend_error",
        f"Tool '{tool_name}' failed in backend execution: {exc}",
        "Check the target id, parameters, and backend dependency state before retrying.",
        retryable=False,
        details={"exception_type": exc.__class__.__name__},
    )


def _tool_error(
    tool_name: str,
    code: str,
    message: str,
    hint: str,
    *,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    return ToolResult(
        status="error",
        error=ToolError(
            message=message,
            code=code,
            hint=hint,
            retryable=retryable,
            details={"tool": tool_name, **(details or {})},
        ),
    )
