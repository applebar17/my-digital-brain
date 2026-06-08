from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from my_digital_brain.ai.models import ToolError, ToolResult
from my_digital_brain.agentic.contexts import CorrectionProposalContext
from my_digital_brain.agentic.enums import AgenticStateId, ConfirmationRiskLevel, CorrectionAction
from my_digital_brain.agentic.runtime_models import AgenticToolEvent
from my_digital_brain.core.ids import new_uuid


@dataclass(slots=True)
class AgenticToolExecutionContext:
    state_id: str | None = None
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

    def _handle_propose_memory_correction(
        self,
        correction_text: str,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        if self._is_handoff_state():
            return _handoff_result(
                "propose_memory_correction",
                "correction_intake",
                {
                    "correction_text": correction_text,
                    "target_id": target_id,
                    "metadata": metadata or {},
                },
                output="Memory correction handoff requested.",
            )
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

    def _handle_request_contradiction_review(
        self,
        agent_doubt: str,
        proposed_write_ref: str | None = None,
        proposed_write: dict[str, Any] | None = None,
        affected_entity_refs: list[str] | None = None,
        affected_relationship_refs: list[str] | None = None,
        source_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        if not (proposed_write_ref or proposed_write):
            return _tool_error(
                "request_contradiction_review",
                "missing_contradiction_write_context",
                "Contradiction review requires a proposed write reference or payload.",
                "Pass proposed_write_ref or proposed_write so the judge can inspect the conflict.",
                retryable=True,
            )
        return _handoff_result(
            "request_contradiction_review",
            "contradiction_review",
            {
                "agent_doubt": agent_doubt,
                "proposed_write_ref": proposed_write_ref,
                "proposed_write": proposed_write or {},
                "affected_entity_refs": affected_entity_refs or [],
                "affected_relationship_refs": affected_relationship_refs or [],
                "source_refs": source_refs or [],
                "metadata": metadata or {},
            },
            output="Contradiction review handoff requested.",
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
    if state_id == AgenticStateId.CORRECTION_INTAKE.value:
        return PendingProcessKind.MEMORY_CORRECTION.value
    return PendingProcessKind.MEMORY_INGESTION.value


def _clarification_resume_strategy(state_id: str) -> str:
    return {
        AgenticStateId.PLANNING_CHECKPOINT.value: "planning_checkpoint",
        AgenticStateId.MEMORY_INGESTION_PLANNING.value: "memory_ingestion_planning",
        AgenticStateId.CONTRADICTION_REVIEW.value: "contradiction_review",
        AgenticStateId.MEMORY_QUERY.value: "memory_query",
        AgenticStateId.CORRECTION_INTAKE.value: "correction_intake",
        AgenticStateId.PENDING_PROCESS_REVIEW.value: "pending_process_review",
        AgenticStateId.REASONING_CHECKPOINT.value: "reasoning_checkpoint",
    }.get(state_id, "pending_process_review")


def _handoff_result(
    operation: str,
    handoff_target: str,
    handoff_arguments: dict[str, Any],
    *,
    output: str,
) -> ToolResult:
    return ToolResult(
        status="ok",
        output=output,
        data={
            "operation": operation,
            "handoff_target": handoff_target,
            "handoff_arguments": {
                key: value
                for key, value in handoff_arguments.items()
                if value not in (None, "", [])
            },
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
