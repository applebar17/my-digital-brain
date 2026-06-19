from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.models import ToolError, ToolResult
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
    pending_process_context: Any | None = None
    pending_process_contexts: list[Any] = field(default_factory=list)
    conversation_history_refs: list[str] = field(default_factory=list)
    tool_events: list[AgenticToolEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgenticToolBindings:
    def __init__(self, context: AgenticToolExecutionContext) -> None:
        self.context = context

    def handler_for(self, handler_key: str):
        handler = getattr(self, f"_handle_{handler_key}", None)
        if handler is None:
            raise ValueError(f"No agentic tool handler registered for key: {handler_key}")
        return handler

    def _handle_start_memory_ingestion(
        self,
        source_text: str,
        source_refs: list[str] | None = None,
        pending_process_policy: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        if self._is_handoff_state():
            return _handoff_result(
                "start_memory_ingestion",
                "memory_ingestion_precheck",
                {
                    "source_text": source_text,
                    "source_refs": source_refs or [],
                    "pending_process_policy": pending_process_policy,
                    "metadata": metadata or {},
                },
                output="Memory ingestion handoff requested.",
            )
        request = self._chat_request(
            source_text,
            metadata={
                "source_refs": source_refs or [],
                "pending_process_policy": pending_process_policy,
                **(metadata or {}),
            },
        )
        if isinstance(request, ToolResult):
            return request
        return self._facade_call("start_memory_ingestion", request)

    def _handle_query_memory_context(
        self,
        question: str,
        seed_id: str | None = None,
        desired_view: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        if self._is_handoff_state():
            return _handoff_result(
                "query_memory_context",
                "memory_query",
                {
                    "question": question,
                    "seed_id": seed_id,
                    "desired_view": desired_view,
                    "metadata": metadata or {},
                },
                output="Memory query handoff requested.",
            )
        request = self._chat_request(
            question,
            metadata={
                "seed_id": seed_id,
                "desired_view": desired_view,
                **(metadata or {}),
            },
        )
        if isinstance(request, ToolResult):
            return request
        return self._facade_call("query_memory_context", request)

    def _handle_update_memory_graph(
        self,
        source_text: str,
        guidelines: str | None = None,
        desired_work: str | None = None,
        target_ids: list[str] | None = None,
        source_refs: list[str] | None = None,
        pending_process_policy: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        arguments = {
            "source_text": source_text,
            "guidelines": guidelines
            or "Update the memory graph using deterministic graph tools.",
            "desired_work": desired_work,
            "target_ids": target_ids or [],
            "source_refs": source_refs or [],
            "pending_process_policy": pending_process_policy,
            "metadata": metadata or {},
        }
        if self._is_handoff_state():
            return _handoff_result(
                "update_memory_graph",
                "graph_update",
                arguments,
                output="Graph update handoff requested.",
            )
        request = self._chat_request(source_text, metadata=arguments)
        if isinstance(request, ToolResult):
            return request
        return self._facade_call("update_memory_graph", request)

    def _handle_get_conversation_status(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        request = self._chat_request(self.context.current_text or "", metadata=metadata or {})
        if isinstance(request, ToolResult):
            return request
        return self._facade_call("get_conversation_status", request)

    def _handle_cancel_pending_process(
        self,
        pending_process_id: str | None = None,
        reason: str | None = None,
    ) -> ToolResult:
        selection = self._select_pending_process(
            "cancel_pending_process",
            pending_process_id,
        )
        if isinstance(selection, ToolResult):
            return selection
        if not self.context.session_id or not self.context.owner_id:
            return _missing_runtime_context(
                "cancel_pending_process",
                ["session_id", "owner_id"],
            )
        from my_digital_brain.chat.facade import CancelPendingProcessRequest
        from my_digital_brain.chat.enums import PendingProcessStatus

        process_id, pending_context = selection
        request = CancelPendingProcessRequest(
            session_id=self.context.session_id,
            owner_id=self.context.owner_id,
            pending_process_id=process_id,
            reason=reason,
            metadata={"discard_resumable_checkpoint": True},
        )
        if self.context.chat_store is not None:
            try:
                self.context.chat_store.update_pending_process_status(
                    self.context.session_id,
                    process_id,
                    PendingProcessStatus.CANCELLED,
                    metadata={
                        "cancel_reason": reason,
                        "resumable": False,
                    },
                    context_updates={"resumable": False},
                )
            except Exception as exc:
                return _exception_result("cancel_pending_process", exc)
        if self.context.backend_facade is not None:
            result = self._facade_call("cancel_pending_process", request)
            result.data = {
                **(result.data or {}),
                "operation": "cancel_pending_process",
                "pending_process_id": process_id,
                "pending_process_summary": _compact_pending_context(pending_context),
                "clear_pending_process": True,
            }
            return result
        return ToolResult(
            status="ok",
            output="Pending process cancelled.",
            data={
                "operation": "cancel_pending_process",
                "pending_process_id": process_id,
                "pending_process_summary": _compact_pending_context(pending_context),
                "clear_pending_process": True,
            },
        )

    def _handle_resume_pending_process(
        self,
        pending_process_id: str | None = None,
    ) -> ToolResult:
        selection = self._select_pending_process(
            "resume_pending_process",
            pending_process_id,
        )
        if isinstance(selection, ToolResult):
            return selection
        process_id, pending_context = selection
        request = self._chat_request(
            self.context.current_text or "",
            metadata={
                "pending_process_id": process_id,
                "resume_policy": "refresh_context_before_write",
            },
            pending_process_context=pending_context,
        )
        if isinstance(request, ToolResult):
            return request
        facade = self.context.backend_facade
        if facade is None:
            return _missing_dependency("resume_pending_process", "backend_facade")
        if not hasattr(facade, "resume_pending_process"):
            return _tool_error(
                "resume_pending_process",
                "unsupported_backend_facade",
                "The configured backend facade cannot resume pending processes.",
                "Configure a facade with resume_pending_process or ask the user to restart the memory.",
                retryable=False,
            )
        result = self._facade_call("resume_pending_process", request)
        result_payload = result.data.get("result") if result.data else None
        result_metadata = (
            result_payload.get("metadata")
            if isinstance(result_payload, dict)
            and isinstance(result_payload.get("metadata"), dict)
            else {}
        )
        if (
            self.context.chat_store is not None
            and result.status == "ok"
            and result_metadata.get("clear_pending_process")
        ):
            from my_digital_brain.chat.enums import PendingProcessStatus

            try:
                self.context.chat_store.update_pending_process_status(
                    request.session_id,
                    process_id,
                    PendingProcessStatus.COMPLETED,
                    metadata={
                        "completed_by": "resume_pending_process",
                        "resume_policy": "refresh_context_before_write",
                    },
                    context_updates={"resumable": False},
                )
            except Exception as exc:
                return _exception_result("resume_pending_process", exc)
        result.data = {
            **(result.data or {}),
            "operation": "resume_pending_process",
            "pending_process_id": process_id,
            "pending_process_summary": _compact_pending_context(pending_context),
            "resume_policy": "refresh_context_before_write",
        }
        return result

    def _handle_pause_pending_process(
        self,
        pending_process_id: str | None = None,
        reason: str | None = None,
    ) -> ToolResult:
        selection = self._select_pending_process(
            "pause_pending_process",
            pending_process_id,
        )
        if isinstance(selection, ToolResult):
            return selection
        process_id, pending_context = selection
        if not self.context.session_id:
            return _missing_runtime_context("pause_pending_process", ["session_id"])
        if self.context.chat_store is not None:
            from my_digital_brain.chat.enums import PendingProcessStatus

            try:
                pending_context = self.context.chat_store.update_pending_process_status(
                    self.context.session_id,
                    process_id,
                    PendingProcessStatus.PAUSED,
                    metadata={
                        "pause_reason": reason,
                        "resumable": True,
                    },
                    context_updates={"resumable": True},
                )
            except Exception as exc:
                return _exception_result("pause_pending_process", exc)
        if self.context.backend_facade is not None and hasattr(
            self.context.backend_facade,
            "pause_pending_process",
        ):
            from my_digital_brain.chat.facade import CancelPendingProcessRequest

            request = CancelPendingProcessRequest(
                session_id=self.context.session_id,
                owner_id=self.context.owner_id or "owner",
                pending_process_id=process_id,
                reason=reason,
            )
            result = self._facade_call("pause_pending_process", request)
            result.data = {
                **(result.data or {}),
                "operation": "pause_pending_process",
                "pending_process_id": process_id,
                "pending_process_summary": _compact_pending_context(pending_context),
                "clear_pending_process": True,
            }
            return result
        return ToolResult(
            status="ok",
            output="Pending process paused.",
            data={
                "operation": "pause_pending_process",
                "pending_process_id": process_id,
                "reason": reason,
                "pending_process_summary": _compact_pending_context(pending_context),
                "clear_pending_process": True,
            },
        )

    def _handle_request_user_clarification(
        self,
        reason: str,
        questions: list[dict[str, Any]],
        compact_summary: str | None = None,
        target_refs: list[str] | None = None,
    ) -> ToolResult:
        from my_digital_brain.chat.clarification import build_clarification_packet

        state_id = self.context.state_id or "unknown"
        process_id = self._pending_process_id() or new_uuid()
        try:
            packet = build_clarification_packet(
                process_id=process_id,
                origin_state_id=state_id,
                reason=reason,
                questions=questions,
                compact_summary=compact_summary,
                target_refs=target_refs or [],
            )
        except Exception as exc:
            return _tool_error(
                "request_user_clarification",
                "invalid_clarification_packet",
                f"Clarification questions failed validation: {exc}",
                (
                    "Pass one to three concrete questions. Each question may include "
                    "up to five options with labels."
                ),
                retryable=True,
                details={"exception_type": exc.__class__.__name__},
            )

        question = packet.questions[0].question
        pending_process = {
            "process_id": process_id,
            "kind": _clarification_process_kind(state_id, self.context.pending_process_context),
            "status": "pending",
            "question": question,
            "metadata": {
                "source": "request_user_clarification",
                "state_id": state_id,
                "reason": reason,
                "summary": compact_summary or reason,
                "unresolved_targets": packet.target_refs,
                "clarification_packet": packet.model_dump(mode="json", exclude_none=True),
                "resume_strategy": _clarification_resume_strategy(state_id),
                "checkpoint_schema_version": "clarification_v1",
            },
        }
        return ToolResult(
            status="needs_user_input",
            output=question,
            data={
                "operation": "request_user_clarification",
                "pending_process": pending_process,
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
        return _chat_result_to_tool_result(name, result)

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
        pending_process_context: Any | None = None,
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
            pending_process_context=pending_process_context
            if pending_process_context is not None
            else self.context.pending_process_context,
            conversation_history_refs=list(self.context.conversation_history_refs),
            metadata={
                "sender_id": self.context.sender_id,
                "message_id": self.context.message_id,
                **self.context.metadata,
                **{key: value for key, value in metadata.items() if value is not None},
            },
        )

    def _pending_process_id(self) -> str | None:
        pending = self.context.pending_process_context
        if pending is None:
            return None
        process_ref = getattr(pending, "process_ref", None)
        if process_ref is not None:
            return getattr(process_ref, "process_id", None)
        return getattr(pending, "process_id", None)

    def _select_pending_process(
        self,
        tool_name: str,
        pending_process_id: str | None = None,
    ) -> tuple[str, Any] | ToolResult:
        candidates = self._pending_candidates()
        if pending_process_id:
            for candidate in candidates:
                process_id = _pending_context_id(candidate)
                if process_id == pending_process_id:
                    return process_id, candidate
            if self.context.chat_store is not None:
                try:
                    loaded = self.context.chat_store.get_pending_process_context(
                        pending_process_id,
                    )
                    return pending_process_id, loaded
                except Exception:
                    pass
            return _tool_error(
                tool_name,
                "unknown_pending_process",
                f"Pending process '{pending_process_id}' is not available in this context.",
                "Select one of the visible pending process ids or ask the user which process to use.",
                retryable=True,
                details={"available_process_ids": [_pending_context_id(item) for item in candidates]},
            )
        active_id = self._pending_process_id()
        if active_id:
            for candidate in candidates:
                if _pending_context_id(candidate) == active_id:
                    return active_id, candidate
        if len(candidates) == 1:
            process_id = _pending_context_id(candidates[0])
            if process_id:
                return process_id, candidates[0]
        if not candidates:
            return _tool_error(
                tool_name,
                "missing_pending_process",
                "No pending process is available for this action.",
                "Answer normally, start a new memory, or ask the user what they want to do.",
                retryable=False,
            )
        return _tool_error(
            tool_name,
            "ambiguous_pending_process",
            "Multiple pending processes are available and no process id was selected.",
            "Call the tool again with one of the visible pending_process_id values.",
            retryable=True,
            details={"available_process_ids": [_pending_context_id(item) for item in candidates]},
        )

    def _pending_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        if self.context.pending_process_context is not None:
            candidates.append(self.context.pending_process_context)
        for pending in self.context.pending_process_contexts:
            process_id = _pending_context_id(pending)
            if process_id and all(_pending_context_id(item) != process_id for item in candidates):
                candidates.append(pending)
        return candidates

    def _is_handoff_state(self) -> bool:
        return self.context.state_id in {
            AgenticStateId.CONVERSATION_ENTRY.value,
            AgenticStateId.PENDING_PROCESS_REVIEW.value,
        }


def _chat_result_to_tool_result(tool_name: str, result: Any) -> ToolResult:
    payload = _serialize(result)
    status = str(payload.get("status", "ok"))
    is_error = status == "failed"
    return ToolResult(
        status="error" if is_error else "ok",
        output=payload.get("primary_text") or f"{tool_name} completed.",
        data={"operation": tool_name, "result": payload},
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


def _pending_context_id(pending_context: Any) -> str | None:
    process_ref = getattr(pending_context, "process_ref", None)
    if process_ref is not None:
        process_id = getattr(process_ref, "process_id", None)
        return str(process_id) if process_id else None
    process_id = getattr(pending_context, "process_id", None)
    return str(process_id) if process_id else None


def _compact_pending_context(pending_context: Any) -> dict[str, Any]:
    process_ref = getattr(pending_context, "process_ref", None)
    context = getattr(pending_context, "context", {}) or {}
    if process_ref is not None:
        metadata = getattr(process_ref, "metadata", {}) or {}
        return {
            "process_id": getattr(process_ref, "process_id", None),
            "kind": getattr(process_ref, "kind", None),
            "status": getattr(process_ref, "status", None),
            "question": getattr(process_ref, "question", None),
            "compact_summary": context.get("summary"),
            "unresolved_targets": metadata.get("unresolved_targets", []),
        }
    metadata = getattr(pending_context, "metadata", {}) or {}
    return {
        "process_id": getattr(pending_context, "process_id", None),
        "kind": getattr(pending_context, "kind", None),
        "status": getattr(pending_context, "status", None),
        "question": getattr(pending_context, "question", None),
        "compact_summary": getattr(pending_context, "compact_summary", None),
        "unresolved_targets": getattr(pending_context, "unresolved_targets", [])
        or metadata.get("unresolved_targets", []),
    }


def _clarification_process_kind(state_id: str, pending_context: Any | None) -> str:
    from my_digital_brain.chat.enums import PendingProcessKind

    process_ref = getattr(pending_context, "process_ref", None)
    if process_ref is not None:
        kind = getattr(process_ref, "kind", None)
        if kind:
            return str(getattr(kind, "value", kind))
    if state_id == AgenticStateId.MEMORY_QUERY.value:
        return PendingProcessKind.MEMORY_QUERY.value
    if state_id == AgenticStateId.GRAPH_UPDATE.value:
        return PendingProcessKind.MEMORY_UPDATE.value
    return PendingProcessKind.MEMORY_INGESTION.value


def _clarification_resume_strategy(state_id: str) -> str:
    return {
        AgenticStateId.PLANNING_CHECKPOINT.value: "planning_checkpoint",
        AgenticStateId.CONTRADICTION_REVIEW.value: "contradiction_review",
        AgenticStateId.MEMORY_QUERY.value: "memory_query",
        AgenticStateId.GRAPH_UPDATE.value: "graph_update",
        AgenticStateId.PENDING_PROCESS_REVIEW.value: "pending_process_review",
        AgenticStateId.REASONING_CHECKPOINT.value: "reasoning_checkpoint",
    }.get(state_id, "pending_process_review")


def _handoff_result(
    operation: str,
    target_state: str,
    arguments: dict[str, Any],
    *,
    output: str,
) -> ToolResult:
    return ToolResult(
        status="accepted",
        output=output,
        data={
            "operation": operation,
            "handoff_target": target_state,
            "handoff_arguments": arguments,
        },
    )


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
