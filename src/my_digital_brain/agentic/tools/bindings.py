from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.models import ToolError, ToolResult
from my_digital_brain.agentic.contexts import (
    GraphContextPackage,
    GraphUpdateContext,
    MemoryCreationContext,
    MemoryIngestionContext,
    MemoryPlanAction,
    QueryRetrievalPlanningContext,
)
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.runtime_models import AgenticToolEvent
from my_digital_brain.core.ids import new_uuid


GRAPH_UPDATE_CREATABLE_LABELS = {
    "Person",
    "Event",
    "Place",
    "Organization",
    "Object",
    "Animal",
    "SocialCircle",
    "Topic",
    "Source",
    "Claim",
    "Perception",
    "RelationshipContext",
    "ProfileMemory",
    "ContactPoint",
    "ExternalReference",
    "RelationshipState",
    "ChangeRecord",
    "MemoryLog",
    "MediaAsset",
    "ContradictionRecord",
}

GRAPH_UPDATE_BLOCKED_RELATIONSHIP_TYPES = {
    "MERGED_NODE",
    "CANONICAL_NODE",
    "MERGED_INTO",
}


@dataclass(slots=True)
class AgenticToolExecutionContext:
    state_id: str | None = None
    backend_facade: Any | None = None
    graph_service: Any | None = None
    ingestion_service: Any | None = None
    semantic_search_service: Any | None = None
    vectorization_service: Any | None = None
    chat_store: Any | None = None
    session_id: str | None = None
    channel: str = "web"
    conversation_id: str | None = None
    owner_id: str | None = None
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
        ingestion_context = MemoryIngestionContext(
            conversation=conversation,
            graph_context=_graph_context_from_retrieval(retrieval),
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
        pending_process_policy: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        del pending_process_policy
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
            metadata=metadata or {},
        )
        return self._run_child_frame(
            tool_name="update_memory_graph",
            state_id=AgenticStateId.GRAPH_UPDATE,
            payload=update_context,
        )

    def _child_execution_context(self) -> AgenticToolExecutionContext:
        return AgenticToolExecutionContext(
            backend_facade=self.context.backend_facade,
            graph_service=self.context.graph_service,
            ingestion_service=self.context.ingestion_service,
            semantic_search_service=self.context.semantic_search_service,
            vectorization_service=self.context.vectorization_service,
            chat_store=self.context.chat_store,
            session_id=self.context.session_id,
            channel=self.context.channel,
            conversation_id=self.context.conversation_id,
            owner_id=self.context.owner_id,
            sender_id=self.context.sender_id,
            message_id=self.context.message_id,
            current_text=self.context.current_text,
            conversation_history_refs=list(self.context.conversation_history_refs),
            metadata=dict(self.context.metadata),
            frame_id=new_uuid(),
            parent_frame_id=self.context.frame_id,
            parent_tool_call_id=self.context.current_tool_call_id,
            current_tool_call_id=self.context.current_tool_call_id,
            current_tool_name=self.context.current_tool_name,
            current_tool_arguments=dict(self.context.current_tool_arguments),
            provider_messages=list(self.context.provider_messages),
            agentic_runtime=self.context.agentic_runtime,
            conversation_context=self.context.conversation_context,
            current_payload=self.context.current_payload,
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
        semantic = self.context.semantic_search_service or getattr(
            self.context.backend_facade,
            "semantic_search_service",
            None,
        )
        if semantic is None or not query.strip():
            return {
                "status": "skipped",
                "reason": "semantic_search_service_missing" if semantic is None else "empty_query",
                "desired_view": desired_view,
            }
        try:
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

    def _handle_get_conversation_status(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        request = self._chat_request(self.context.current_text or "", metadata=metadata or {})
        if isinstance(request, ToolResult):
            return request
        return self._facade_call("get_conversation_status", request)

    def _handle_request_user_clarification(
        self,
        reason: str,
        questions: list[dict[str, Any]],
        target_refs: list[str] | None = None,
    ) -> ToolResult:
        from my_digital_brain.chat.clarification import build_clarification_packet

        state_id = self.context.state_id or "unknown"
        frame_id = self.context.frame_id or new_uuid()
        self.context.frame_id = frame_id
        try:
            packet = build_clarification_packet(
                frame_id=frame_id,
                origin_state_id=state_id,
                reason=reason,
                questions=questions,
                target_refs=target_refs or [],
            )
        except Exception as exc:
            return _tool_error(
                "request_user_clarification",
                "invalid_clarification_packet",
                f"Clarification questions failed validation: {exc}",
                (
                    "Pass one to three short, direct user-facing questions. Each "
                    "question may include up to five concise option labels."
                ),
                retryable=True,
                details={"exception_type": exc.__class__.__name__},
            )

        question = packet.questions[0].question
        return ToolResult(
            status="interrupted",
            output=question,
            data={
                "operation": "request_user_clarification",
                "frame_id": frame_id,
                "clarification_packet": packet.model_dump(mode="json", exclude_none=True),
                "history_delta": [
                    message.model_dump(mode="json", exclude_none=True)
                    for message in packet.history_delta
                ],
            },
        )

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
                node
                for node in payload.get("nodes", [])
                if node.get("label") == "ContactPoint"
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
            explicit_targets = []
            for target_id in target_ids or []:
                explicit_targets.append(graph.get_node(str(target_id)))
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

            semantic = self.context.semantic_search_service or getattr(
                self.context.backend_facade,
                "semantic_search_service",
                None,
            )
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

    def _handle_create_memory_log(
        self,
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
        host_ids = [str(value) for value in host_target_ids if value]
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
        primary_host = primary_host_target_id or host_ids[0]
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
            primary_node = graph.get_node(primary_host)
            for target_id in [
                *host_ids,
                *(involved_target_ids or []),
                *(relationship_context_target_ids or []),
            ]:
                graph.get_node(str(target_id))
            properties = {
                "log_text": log_text,
                "log_kind": log_kind,
                "source_kind": source_kind or "graph_update",
                "happened_at": happened_at,
                "primary_host_target_id": primary_host,
                "primary_host_target_label": primary_node.label,
                "host_target_ids": host_ids,
                "involved_target_ids": list(involved_target_ids or []),
                "relationship_context_target_ids": list(relationship_context_target_ids or []),
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
            for involved_id in involved_target_ids or []:
                graph.upsert_relationship("INVOLVES", log_id, str(involved_id), {})
            for context_id in relationship_context_target_ids or []:
                graph.upsert_relationship(
                    "UPDATES_RELATIONSHIP",
                    log_id,
                    str(context_id),
                    {},
                )
            refreshed = self._refresh_vectors(
                "create_memory_log",
                [log_id, *host_ids, *(involved_target_ids or []), *(relationship_context_target_ids or [])],
            )
            return _update_tool_result(
                "create_memory_log",
                summary="MemoryLog created and linked.",
                created_refs=[log_id],
                affected_graph_ids=[
                    log_id,
                    *host_ids,
                    *(involved_target_ids or []),
                    *(relationship_context_target_ids or []),
                ],
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"memory_log": _serialize(log)},
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
            refreshed = self._refresh_vectors("create_graph_node", [node_id])
            return _update_tool_result(
                "create_graph_node",
                summary=f"{label} node created.",
                created_refs=[node_id],
                affected_graph_ids=[node_id],
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"node": _serialize(node)},
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
        try:
            node = graph.patch_node(node_id, properties)
            refreshed = self._refresh_vectors("patch_graph_node", [node_id])
            return _update_tool_result(
                "patch_graph_node",
                summary="Graph node patched.",
                updated_refs=[node_id],
                affected_graph_ids=[node_id],
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"node": _serialize(node)},
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
        try:
            relationship = graph.upsert_relationship(
                relationship_type,
                from_id,
                to_id,
                properties,
            )
            relationship_id = str(relationship.properties["id"])
            refreshed = self._refresh_vectors(
                "upsert_graph_relationship",
                [from_id, to_id],
            )
            return _update_tool_result(
                "upsert_graph_relationship",
                summary="Graph relationship upserted.",
                created_refs=[relationship_id],
                affected_graph_ids=[from_id, to_id],
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"relationship": _serialize(relationship)},
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
        try:
            state = graph.create_relationship_state(
                context_id,
                properties,
                make_current=make_current,
            )
            state_id = str(state.properties["id"])
            refreshed = self._refresh_vectors(
                "create_relationship_state",
                [context_id, state_id],
            )
            return _update_tool_result(
                "create_relationship_state",
                summary="RelationshipState created.",
                created_refs=[state_id],
                updated_refs=[context_id] if make_current else [],
                affected_graph_ids=[context_id, state_id],
                refreshed_vector_scopes=refreshed.get("refreshed_vector_scopes", []),
                diagnostics=refreshed.get("diagnostics", []),
                data={"relationship_state": _serialize(state)},
            )
        except Exception as exc:
            return _update_exception_result("create_relationship_state", exc)

    def _refresh_vectors(self, tool_name: str, target_ids: list[str]) -> dict[str, Any]:
        service = (
            self.context.vectorization_service
            or getattr(self.context.ingestion_service, "vectorization_service", None)
            or getattr(self.context.backend_facade, "vectorization_service", None)
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
                "diagnostics": [{"level": "info", "code": "vector_refresh_done", "result": payload}],
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

    def _facade_call(self, name: str, request: Any) -> ToolResult:
        facade = self.context.backend_facade
        if facade is None:
            return _missing_dependency(name, "backend_facade")
        try:
            method = getattr(facade, name)
        except AttributeError:
            return _tool_error(
                name,
                "facade_method_missing",
                f"Backend facade does not implement '{name}'.",
                "Use a configured MemoryBackendToolFacade or avoid this tool in the state.",
                retryable=False,
            )
        try:
            result = method(request)
        except Exception as exc:
            return _exception_result(name, exc)
        tool_result = _chat_result_to_tool_result(name, result)
        if tool_result.status == "interrupted":
            self._normalize_clarification_tool_result(tool_result)
        return tool_result

    def _normalize_clarification_tool_result(self, result: ToolResult) -> None:
        if not isinstance(result.data, dict):
            return
        packet = result.data.get("clarification_packet")
        if not isinstance(packet, dict):
            payload = result.data.get("result")
            if isinstance(payload, dict):
                packet = payload.get("clarification_packet")
        if not isinstance(packet, dict):
            return
        frame_id = self.context.frame_id or new_uuid()
        self.context.frame_id = frame_id
        packet["frame_id"] = frame_id
        result.data["frame_id"] = frame_id
        result.data["clarification_packet"] = packet
        payload = result.data.get("result")
        if isinstance(payload, dict):
            payload["clarification_packet"] = packet

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

    def _chat_request(
        self,
        text: str,
        *,
        metadata: dict[str, Any],
    ) -> Any | ToolResult:
        missing = [
            key
            for key, value in {
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "owner_id": self.context.owner_id,
            }.items()
            if not value
        ]
        if missing:
            return _missing_runtime_context("chat_tool_request", missing)
        from my_digital_brain.chat.facade import ChatToolRequest

        return ChatToolRequest(
            session_id=str(self.context.session_id),
            channel=self.context.channel,
            conversation_id=str(self.context.conversation_id),
            owner_id=str(self.context.owner_id),
            text=text,
            conversation_history_refs=list(self.context.conversation_history_refs),
            metadata={
                "sender_id": self.context.sender_id,
                "message_id": self.context.message_id,
                **self.context.metadata,
                **{key: value for key, value in metadata.items() if value is not None},
            },
        )

    def _is_handoff_state(self) -> bool:
        return self.context.state_id == AgenticStateId.CONVERSATION_ENTRY.value


def _graph_context_from_retrieval(retrieval: dict[str, Any]) -> GraphContextPackage | None:
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
            package_id = str(package.get("package_id") or f"retrieval_package_{index}")
            aliases[package_id] = str(package.get("target_id") or package.get("seed_id") or package_id)
            candidate_matches.append(package)
    hits = result.get("hits") or []
    for hit in hits[:10]:
        if isinstance(hit, dict):
            candidate_matches.append(hit)
    if not aliases and not candidate_matches:
        return None
    return GraphContextPackage(
        aliases=aliases,
        candidate_matches=candidate_matches,
        metadata={"source": "scoped_retrieval"},
    )


def _chat_result_to_tool_result(tool_name: str, result: Any) -> ToolResult:
    payload = _serialize(result)
    status = str(payload.get("status", "ok"))
    is_error = status == "failed"
    is_interrupted = status == "interrupted"
    packet = payload.get("clarification_packet")
    data = {"operation": tool_name, "result": payload}
    if is_interrupted and isinstance(packet, dict):
        data["clarification_packet"] = packet
    return ToolResult(
        status="interrupted" if is_interrupted else "error" if is_error else "ok",
        output=payload.get("primary_text") or f"{tool_name} completed.",
        data=data,
        error=(
            ToolError(
                message=payload.get("primary_text") or f"{tool_name} failed.",
                code="backend_tool_failed",
                hint="Inspect diagnostics and adjust the tool call or ask the user.",
                retryable=False,
                details=payload,
            )
            if is_error
            else None
        ),
    )


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
            "Retry with a JSON object, for example {\"status\":\"active\"}.",
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


def _missing_dependency(tool_name: str, dependency: str) -> ToolResult:
    return _tool_error(
        tool_name,
        "missing_dependency",
        f"Tool '{tool_name}' cannot run because '{dependency}' is not configured.",
        f"Configure AgenticToolExecutionContext.{dependency} or choose a tool that does not need it.",
        retryable=False,
        details={"missing_dependency": dependency},
    )


def _missing_runtime_context(tool_name: str, missing: list[str]) -> ToolResult:
    return _tool_error(
        tool_name,
        "missing_runtime_context",
        f"Tool '{tool_name}' is missing required runtime context: {', '.join(missing)}.",
        "Pass session/conversation/owner context before exposing chat facade tools.",
        retryable=False,
        details={"missing_fields": missing},
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
