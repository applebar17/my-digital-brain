from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from my_digital_brain.ai.models import ToolError, ToolResult
from my_digital_brain.agentic.contexts import CorrectionProposalContext
from my_digital_brain.agentic.enums import ConfirmationRiskLevel, CorrectionAction
from my_digital_brain.chat.facade import CancelPendingProcessRequest, ChatToolRequest
from my_digital_brain.core.ids import new_uuid


@dataclass(slots=True)
class AgenticToolExecutionContext:
    backend_facade: Any | None = None
    graph_service: Any | None = None
    ingestion_service: Any | None = None
    chat_store: Any | None = None
    session_id: str | None = None
    channel: str = "web"
    conversation_id: str | None = None
    owner_id: str | None = None
    sender_id: str | None = None
    message_id: str | None = None
    current_text: str | None = None
    pending_process_context: Any | None = None
    conversation_history_refs: list[str] = field(default_factory=list)
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

    def _handle_propose_memory_correction(
        self,
        correction_text: str,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        request = self._chat_request(
            correction_text,
            metadata={"target_id": target_id, **(metadata or {})},
        )
        if isinstance(request, ToolResult):
            return request
        return self._facade_call("propose_memory_correction", request)

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
        if self.context.backend_facade is None:
            return _missing_dependency("cancel_pending_process", "backend_facade")
        if not self.context.session_id or not self.context.owner_id:
            return _missing_runtime_context(
                "cancel_pending_process",
                ["session_id", "owner_id"],
            )
        request = CancelPendingProcessRequest(
            session_id=self.context.session_id,
            owner_id=self.context.owner_id,
            pending_process_id=pending_process_id or self._pending_process_id(),
            reason=reason,
        )
        return self._facade_call("cancel_pending_process", request)

    def _handle_resume_pending_process(
        self,
        user_reply: str,
        pending_process_id: str | None = None,
    ) -> ToolResult:
        process_id = pending_process_id or self._pending_process_id()
        if not process_id:
            return _tool_error(
                "resume_pending_process",
                "missing_pending_process",
                "No pending process id is available to resume.",
                "Call start_memory_ingestion, query_memory_context, or answer normally instead.",
                retryable=False,
            )
        return ToolResult(
            status="ok",
            output="Pending process resume request captured.",
            data={
                "operation": "resume_pending_process",
                "pending_process_id": process_id,
                "user_reply": user_reply,
            },
        )

    def _handle_pause_pending_process(
        self,
        pending_process_id: str | None = None,
        reason: str | None = None,
    ) -> ToolResult:
        process_id = pending_process_id or self._pending_process_id()
        return ToolResult(
            status="ok",
            output="Pending process pause request captured.",
            data={
                "operation": "pause_pending_process",
                "pending_process_id": process_id,
                "reason": reason,
            },
        )

    def _handle_request_graph_context_expansion(
        self,
        query: str | None = None,
        seed_id: str | None = None,
        limit: int = 10,
    ) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _missing_dependency("request_graph_context_expansion", "graph_service")
        try:
            data: dict[str, Any] = {"operation": "request_graph_context_expansion"}
            if seed_id:
                data["context_package"] = _serialize(
                    graph.get_context_package(
                        seed_id,
                        include_history=True,
                        timeline_limit=min(limit, 20),
                        relationship_limit=min(limit, 50),
                    ),
                )
            if query:
                data["matches"] = _serialize(graph.search_nodes(query=query, limit=limit))
            return ToolResult(status="ok", output="Graph context expanded.", data=data)
        except Exception as exc:
            return _exception_result("request_graph_context_expansion", exc)

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

    def _handle_resolve_correction_target(
        self,
        correction_text: str,
        target_id: str | None = None,
        limit: int = 5,
    ) -> ToolResult:
        graph = self.context.graph_service
        if graph is None:
            return _missing_dependency("resolve_correction_target", "graph_service")
        try:
            if target_id:
                target = graph.get_node(target_id)
                return ToolResult(
                    status="ok",
                    output="Correction target resolved.",
                    data={
                        "operation": "resolve_correction_target",
                        "target": _serialize(target),
                        "requires_clarification": False,
                    },
                )
            matches = graph.search_nodes(query=correction_text, limit=limit)
            serialized = _serialize(matches)
            return ToolResult(
                status="ok",
                output="Correction target candidates retrieved.",
                data={
                    "operation": "resolve_correction_target",
                    "candidates": serialized,
                    "requires_clarification": len(serialized) != 1,
                },
            )
        except Exception as exc:
            return _exception_result("resolve_correction_target", exc)

    def _handle_build_correction_proposal(
        self,
        correction_text: str,
        target_id: str,
        reason: str,
        target_label: str | None = None,
        field_path: str | None = None,
        current_value: dict[str, Any] | None = None,
        proposed_value: dict[str, Any] | None = None,
        risk_level: str | None = None,
    ) -> ToolResult:
        try:
            proposal = CorrectionProposalContext(
                correction_text=correction_text,
                action=CorrectionAction.PATCH_NODE,
                target_id=target_id,
                target_label=target_label,
                field_path=field_path,
                current_value=current_value,
                proposed_value=proposed_value,
                reason=reason,
                requires_confirmation=True,
                risk_level=risk_level or ConfirmationRiskLevel.MEDIUM,
            )
        except ValidationError as exc:
            return _tool_error(
                "build_correction_proposal",
                "invalid_correction_proposal",
                "Correction proposal arguments failed validation.",
                "Provide target_id, correction_text, and a grounded reason.",
                details={"errors": exc.errors()},
            )
        return ToolResult(
            status="ok",
            output="Correction proposal built. It still requires user confirmation.",
            data={"operation": "build_correction_proposal", "proposal": _serialize(proposal)},
        )

    def _handle_request_user_confirmation(
        self,
        question: str,
        proposal: dict[str, Any],
        target_refs: list[str] | None = None,
    ) -> ToolResult:
        confirmation = {
            "confirmation_id": new_uuid(),
            "question": question,
            "proposal": proposal,
            "target_refs": target_refs or [],
            "required_user_action": "confirm_or_cancel",
        }
        return ToolResult(
            status="ok",
            output=question,
            data={"operation": "request_user_confirmation", "confirmation": confirmation},
        )

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
    ) -> ChatToolRequest | ToolResult:
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
        return ChatToolRequest(
            session_id=str(self.context.session_id),
            channel=self.context.channel,
            conversation_id=str(self.context.conversation_id),
            owner_id=str(self.context.owner_id),
            text=text,
            pending_process_context=self.context.pending_process_context,
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
