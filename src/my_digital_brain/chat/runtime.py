from __future__ import annotations

from contextlib import nullcontext
from typing import Literal

from my_digital_brain.agentic.contexts import (
    ChannelSessionMetadata,
    ConversationContext as AgenticConversationContext,
    GraphUpdateContext,
    PendingProcessContext as AgenticPendingProcessContext,
)
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime import AgenticRuntime
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.chat.agentic_renderer import render_agentic_chat_response
from my_digital_brain.chat.clarification import (
    render_clarification_questions,
    summarize_clarification_answers,
    validate_clarification_answers,
)
from my_digital_brain.chat.enums import (
    ChatChannel,
    ChatDiagnosticLevel,
    ChatResponseStatus,
    ConversationStatus,
    ConversationMessageRole,
    PendingProcessKind,
    PendingProcessStatus,
)
from my_digital_brain.chat.exceptions import ChatValidationError
from my_digital_brain.chat.facade import (
    BackendToolFacade,
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
    NoopBackendToolFacade,
)
from my_digital_brain.chat.models import (
    ChatResponse,
    ChatDiagnostic,
    ConversationMessage,
    ConversationSession,
    ConversationSessionList,
    ConversationSessionDetail,
    ClarificationAnswerPacket,
    ClarificationPacket,
    IncomingChatMessage,
    PendingProcessContext,
)
from my_digital_brain.chat.store import ChatSessionStore, InMemoryChatSessionStore
from my_digital_brain.debug import ai_flow_trace_session, get_ai_flow_trace_store


class ChatRuntime:
    def __init__(
        self,
        store: ChatSessionStore | None = None,
        tool_facade: BackendToolFacade | None = None,
        *,
        runtime_mode: Literal["deterministic", "agentic"] = "deterministic",
        agentic_runtime: AgenticRuntime | None = None,
        graph_service: object | None = None,
        ingestion_service: object | None = None,
        history_service: AgenticHistoryService | None = None,
        debug_commands_enabled: bool = False,
        ai_flow_debug_enabled: bool = False,
        runtime_unavailable_reason: str | None = None,
    ) -> None:
        self.store = store or InMemoryChatSessionStore()
        self.tool_facade = tool_facade or NoopBackendToolFacade()
        self.runtime_mode = runtime_mode
        self.agentic_runtime = agentic_runtime
        self.graph_service = graph_service
        self.ingestion_service = ingestion_service
        self.history_service = history_service or AgenticHistoryService()
        self.debug_commands_enabled = debug_commands_enabled
        self.ai_flow_debug_enabled = ai_flow_debug_enabled
        self.runtime_unavailable_reason = runtime_unavailable_reason

    @traceable(name="Chat Runtime Handle Message", run_type="chain")
    def handle_message(self, message: IncomingChatMessage) -> ChatResponse:
        if not (message.text and message.text.strip()) and not message.media_refs:
            raise ChatValidationError("Incoming chat message must include text or media.")

        session = self._resolve_session(message)

        self.store.append_message(
            ConversationMessage(
                session_id=session.session_id,
                channel_message_id=message.message_id,
                role=ConversationMessageRole.USER,
                text=message.text,
                media_refs=message.media_refs,
                pending_process_id=message.pending_process_id
                or session.active_pending_process_id,
                metadata={
                    "sender_id": message.sender_id,
                    "reply_to_message_id": message.reply_to_message_id,
                    "received_at": message.received_at.isoformat(),
                    **message.metadata,
                },
            ),
        )

        pending_context = self.store.get_active_pending_process_context(session.session_id)
        pending_contexts = self._pending_process_contexts(session.session_id)
        history_refs = self._history_refs(
            session.session_id,
            explicit_refs=message.conversation_history_refs,
        )
        if self._uses_agentic_runtime(message):
            response = self._call_agentic(
                message,
                session.session_id,
                pending_context,
                pending_contexts,
                history_refs,
            )
            result = None
        else:
            result = self._call_facade(message, session.session_id, pending_context, history_refs)
            response = ChatResponse(
                session_id=session.session_id,
                status=result.status,
                primary_text=result.primary_text,
                pending_process=result.pending_process,
                clarification_packet=result.clarification_packet,
                actions=result.actions,
                evidence=result.evidence,
                diagnostics=result.diagnostics,
                metadata=result.metadata,
            )

        self._persist_response(
            session.session_id,
            response,
            source_message_id=message.message_id,
            source_text=message.text,
            history_refs=history_refs,
        )
        return response

    def _persist_response(
        self,
        session_id: str,
        response: ChatResponse,
        *,
        source_message_id: str | None,
        source_text: str | None,
        history_refs: list[str],
    ) -> None:
        if response.pending_process is not None:
            clarification_packet = (
                response.clarification_packet.model_dump(mode="json", exclude_none=True)
                if response.clarification_packet is not None
                else response.pending_process.metadata.get("clarification_packet")
            )
            pending_source_text = response.pending_process.metadata.get("source_text") or source_text
            self.store.save_pending_process_context(
                session_id,
                PendingProcessContext(
                    process_ref=response.pending_process,
                    conversation_history_refs=history_refs,
                    context={
                        "source_message_id": source_message_id,
                        "source_text": pending_source_text,
                        "summary": response.pending_process.metadata.get("summary")
                        or self._pending_summary(
                            pending_source_text,
                            response.pending_process.question,
                        ),
                        "unresolved_targets": response.pending_process.metadata.get(
                            "unresolved_targets",
                            [],
                        ),
                        "checkpoint_schema_version": "v1",
                        "resume_step": "source_reprocess",
                        "pending_question": response.pending_process.question,
                        **(
                            {"clarification_packet": clarification_packet}
                            if clarification_packet
                            else {}
                        ),
                        **(
                            {
                                "clarification_resume": {
                                    "origin_state_id": response.pending_process.metadata.get(
                                        "state_id",
                                    ),
                                    "resume_strategy": response.pending_process.metadata.get(
                                        "resume_strategy",
                                    ),
                                    "checkpoint_schema_version": (
                                        response.pending_process.metadata.get(
                                            "checkpoint_schema_version",
                                        )
                                        or "clarification_v1"
                                    ),
                                }
                            }
                            if clarification_packet
                            else {}
                        ),
                    },
                ),
            )
        elif response.metadata.get("clear_pending_process"):
            self.store.clear_active_pending_process(session_id)

        self.store.append_message(
            ConversationMessage(
                session_id=session_id,
                role=ConversationMessageRole.ASSISTANT,
                text=self._assistant_history_text(response),
                pending_process_id=(
                    response.pending_process.process_id if response.pending_process else None
                ),
                metadata={
                    "response_id": response.response_id,
                    "status": response.status,
                    **(
                        {
                            "clarification_packet": response.clarification_packet.model_dump(
                                mode="json",
                                exclude_none=True,
                            ),
                            "history_delta": [
                                message.model_dump(mode="json", exclude_none=True)
                                for message in response.clarification_packet.history_delta
                            ],
                        }
                        if response.clarification_packet is not None
                        else {}
                    ),
                },
            ),
        )

    def _assistant_history_text(self, response: ChatResponse) -> str:
        if response.clarification_packet is not None:
            for message in response.clarification_packet.history_delta:
                if message.role == ConversationMessageRole.ASSISTANT:
                    return message.content
            return render_clarification_questions(response.clarification_packet)
        return response.primary_text

    def get_session_detail(self, session_id: str, limit: int = 50) -> ConversationSessionDetail:
        return self.store.get_session_detail(session_id, limit=limit)

    def create_session(
        self,
        *,
        channel: ChatChannel | str,
        owner_id: str,
        title: str | None = None,
        external_conversation_id: str | None = None,
    ) -> ConversationSession:
        return self.store.create_session(
            channel=channel,
            owner_id=owner_id,
            title=title,
            external_conversation_id=external_conversation_id,
        )

    def list_sessions(
        self,
        *,
        owner_id: str,
        channel: ChatChannel | str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> ConversationSessionList:
        return ConversationSessionList(
            sessions=self.store.list_sessions(
                owner_id=owner_id,
                channel=channel,
                include_archived=include_archived,
                limit=limit,
            ),
        )

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        status: ConversationStatus | str | None = None,
    ) -> ConversationSession:
        updated: ConversationSession | None = None
        if title is not None:
            updated = self.store.rename_session(session_id, title)
        if status is not None:
            normalized_status = ConversationStatus(status)
            if normalized_status == ConversationStatus.ARCHIVED:
                updated = self.store.archive_session(session_id)
            elif updated is None:
                session = self.store.get_session(session_id)
                updated = self.store.save_session(
                    session.model_copy(
                        update={"status": normalized_status, "archived_at": None},
                        deep=True,
                    ),
                )
        return updated or self.store.get_session(session_id)

    def cancel_session_process(
        self,
        session_id: str,
        *,
        owner_id: str,
        reason: str | None = None,
    ) -> ChatResponse:
        session = self.store.get_session(session_id)
        result = self.tool_facade.cancel_pending_process(
            CancelPendingProcessRequest(
                session_id=session.session_id,
                pending_process_id=session.active_pending_process_id,
                owner_id=owner_id,
                reason=reason,
            ),
        )
        if session.active_pending_process_id is not None:
            self.store.update_pending_process_status(
                session.session_id,
                session.active_pending_process_id,
                PendingProcessStatus.CANCELLED,
                metadata={"cancel_reason": reason, "resumable": False},
                context_updates={"resumable": False},
            )
        else:
            self.store.clear_active_pending_process(session.session_id)
        response = ChatResponse(
            session_id=session.session_id,
            status=result.status,
            primary_text=result.primary_text,
            actions=result.actions,
            evidence=result.evidence,
            diagnostics=result.diagnostics,
            metadata=result.metadata,
        )
        self.store.append_message(
            ConversationMessage(
                session_id=session.session_id,
                role=ConversationMessageRole.ASSISTANT,
                text=response.primary_text,
                metadata={"response_id": response.response_id, "status": response.status},
            ),
        )
        return response

    @traceable(name="Chat Runtime Answer Clarification", run_type="chain")
    def answer_clarification(
        self,
        session_id: str,
        *,
        owner_id: str,
        sender_id: str,
        message_id: str,
        answer_packet: ClarificationAnswerPacket,
    ) -> ChatResponse:
        session = self.store.get_session(session_id)
        if session.owner_id != owner_id:
            raise ChatValidationError("Chat session does not belong to the request owner.")
        pending_context = self.store.get_pending_process_context(answer_packet.process_id)
        if pending_context.process_ref.process_id != session.active_pending_process_id:
            raise ChatValidationError(
                "Clarification answers must target the active pending process.",
            )
        packet = self._clarification_packet_from_pending(pending_context)
        validate_clarification_answers(packet, answer_packet)
        answer_summary = summarize_clarification_answers(packet, answer_packet)

        self.store.append_message(
            ConversationMessage(
                session_id=session.session_id,
                channel_message_id=message_id,
                role=ConversationMessageRole.USER,
                text=answer_summary,
                pending_process_id=pending_context.process_ref.process_id,
                metadata={
                    "sender_id": sender_id,
                    "clarification_answer_packet": answer_packet.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "clarification_answer_summary": answer_summary,
                },
            ),
        )
        resumed_context = pending_context.model_copy(
            update={
                "context": {
                    **pending_context.context,
                    "clarification_answer_packet": answer_packet.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "clarification_answer_summary": answer_summary,
                },
            },
            deep=True,
        )
        if (
            str(pending_context.process_ref.kind) == PendingProcessKind.MEMORY_UPDATE.value
            and self.agentic_runtime is not None
        ):
            response = self._resume_graph_update_clarification(
                session,
                owner_id=owner_id,
                sender_id=sender_id,
                message_id=message_id,
                pending_context=resumed_context,
                answer_summary=answer_summary,
                answer_packet=answer_packet,
            )
        else:
            result = self.tool_facade.resume_pending_process(
                ChatToolRequest(
                    session_id=session.session_id,
                    channel=str(session.channel),
                    conversation_id=session.external_conversation_id,
                    owner_id=owner_id,
                    text=answer_summary,
                    pending_process_context=resumed_context,
                    conversation_history_refs=pending_context.conversation_history_refs,
                    metadata={
                        "message_id": message_id,
                        "clarification_answer_packet": answer_packet.model_dump(
                            mode="json",
                            exclude_none=True,
                        ),
                        "clarification_answer_summary": answer_summary,
                    },
                ),
            )
            response = ChatResponse(
                session_id=session.session_id,
                status=result.status,
                primary_text=result.primary_text,
                pending_process=result.pending_process,
                clarification_packet=result.clarification_packet,
                actions=result.actions,
                evidence=result.evidence,
                diagnostics=result.diagnostics,
                metadata={
                    **result.metadata,
                    "operation": "answer_clarification",
                    "resumed_operation": result.metadata.get(
                        "resumed_operation",
                        "resume_pending_process",
                    ),
                },
            )
        if response.metadata.get("clear_pending_process"):
            self.store.update_pending_process_status(
                session.session_id,
                pending_context.process_ref.process_id,
                PendingProcessStatus.COMPLETED,
                metadata={
                    "completed_by": "answer_clarification",
                    "clarification_answer_summary": answer_summary,
                },
                context_updates={
                    "resumable": False,
                    "clarification_answer_summary": answer_summary,
                },
            )
        self._persist_response(
            session.session_id,
            response,
            source_message_id=message_id,
            source_text=answer_summary,
            history_refs=pending_context.conversation_history_refs,
        )
        return response

    def _resume_graph_update_clarification(
        self,
        session: ConversationSession,
        *,
        owner_id: str,
        sender_id: str,
        message_id: str,
        pending_context: PendingProcessContext,
        answer_summary: str,
        answer_packet: ClarificationAnswerPacket,
    ) -> ChatResponse:
        if self.agentic_runtime is None:
            raise ChatValidationError("Agentic runtime mode requires an AgenticRuntime.")
        original_text = str(
            pending_context.context.get("source_text")
            or pending_context.context.get("original_text")
            or pending_context.process_ref.metadata.get("source_text")
            or "",
        ).strip()
        source_text = "\n\n".join(
            item for item in [original_text, answer_summary] if item
        ) or answer_summary
        incoming = IncomingChatMessage(
            channel=session.channel,
            session_id=session.session_id,
            conversation_id=session.external_conversation_id,
            sender_id=sender_id,
            owner_id=owner_id,
            message_id=message_id,
            text=answer_summary,
            pending_process_id=pending_context.process_ref.process_id,
            conversation_history_refs=pending_context.conversation_history_refs,
            metadata={
                "clarification_answer_packet": answer_packet.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "clarification_answer_summary": answer_summary,
                "timezone": pending_context.context.get("timezone", "UTC"),
            },
        )
        conversation_context = self._agentic_conversation_context(
            incoming,
            session.session_id,
            pending_context,
            self._pending_process_contexts(session.session_id),
        )
        graph_update_context = GraphUpdateContext(
            source_text=source_text,
            conversation=conversation_context,
            guidelines=str(
                pending_context.context.get("guidelines")
                or pending_context.process_ref.metadata.get("guidelines")
                or "Update the memory graph using deterministic tools.",
            ),
            desired_work=(
                pending_context.context.get("desired_work")
                or pending_context.process_ref.metadata.get("desired_work")
            ),
            target_ids=[
                str(target_id)
                for target_id in (
                    pending_context.context.get("target_ids")
                    or pending_context.process_ref.metadata.get("target_ids")
                    or pending_context.context.get("unresolved_targets")
                    or []
                )
            ],
            source_refs=list(
                pending_context.context.get("source_refs")
                or pending_context.process_ref.metadata.get("source_refs")
                or []
            ),
            timezone=str(pending_context.context.get("timezone") or "UTC"),
            metadata={
                "clarification_answer_packet": answer_packet.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "clarification_answer_summary": answer_summary,
                "resumed_from_pending_process_id": pending_context.process_ref.process_id,
            },
        )
        execution_context = AgenticToolExecutionContext(
            backend_facade=self.tool_facade,
            graph_service=self.graph_service,
            ingestion_service=self.ingestion_service,
            chat_store=self.store,
            session_id=session.session_id,
            channel=str(session.channel),
            conversation_id=session.external_conversation_id,
            owner_id=owner_id,
            sender_id=sender_id,
            message_id=message_id,
            current_text=answer_summary,
            pending_process_context=pending_context,
            pending_process_contexts=self._pending_process_contexts(session.session_id),
            conversation_history_refs=pending_context.conversation_history_refs,
            metadata=graph_update_context.metadata,
        )
        result = self.agentic_runtime.run(
            conversation_context,
            execution_context,
            start_state=AgenticStateId.GRAPH_UPDATE,
            start_payload=graph_update_context,
        )
        response = render_agentic_chat_response(result, session_id=session.session_id)
        metadata = {
            **response.metadata,
            "operation": "answer_clarification",
            "resumed_operation": "graph_update",
        }
        if response.pending_process is None and response.status != ChatResponseStatus.NEEDS_USER_INPUT:
            metadata["clear_pending_process"] = True
        return response.model_copy(update={"metadata": metadata}, deep=True)

    def _call_facade(
        self,
        message: IncomingChatMessage,
        session_id: str,
        pending_context: PendingProcessContext | None,
        history_refs: list[str],
    ):
        text = (message.text or "").strip()
        lower_text = text.lower()
        request = ChatToolRequest(
            session_id=session_id,
            channel=str(ChatChannel(message.channel)),
            conversation_id=message.conversation_id,
            owner_id=message.owner_id,
            text=text,
            pending_process_context=pending_context,
            conversation_history_refs=history_refs,
            metadata={
                "message_id": message.message_id,
                "media_refs": [media.model_dump(mode="json") for media in message.media_refs],
            },
        )

        if self.debug_commands_enabled and (
            lower_text == "/status" or lower_text.startswith("/status ")
        ):
            return self.tool_facade.get_conversation_status(request)
        if self.debug_commands_enabled and (
            lower_text == "/cancel" or lower_text.startswith("/cancel ")
        ):
            process_id = pending_context.process_ref.process_id if pending_context else None
            result = self.tool_facade.cancel_pending_process(
                CancelPendingProcessRequest(
                    session_id=session_id,
                    pending_process_id=process_id,
                    owner_id=message.owner_id,
                    reason=text[7:].strip() if len(text) > 7 else None,
                ),
            )
            if process_id is not None:
                self.store.update_pending_process_status(
                    session_id,
                    process_id,
                    PendingProcessStatus.CANCELLED,
                    metadata={
                        "cancel_reason": text[7:].strip() if len(text) > 7 else None,
                        "resumable": False,
                    },
                    context_updates={"resumable": False},
                )
            return result.model_copy(
                update={"metadata": {**result.metadata, "clear_pending_process": True}},
                deep=True,
            )
        if self.debug_commands_enabled and lower_text.startswith("/ask"):
            return self.tool_facade.query_memory_context(
                request.model_copy(update={"text": text[4:].strip() or text}, deep=True),
            )
        if self.debug_commands_enabled and lower_text.startswith("/correct"):
            return self.tool_facade.update_memory_graph(
                request.model_copy(
                    update={
                        "text": text[8:].strip() or text,
                        "metadata": {
                            **request.metadata,
                            "guidelines": "Apply this as a correction or update to the memory graph.",
                            "desired_work": "correct_or_update_memory_graph",
                        },
                    },
                    deep=True,
                ),
            )

        return self._runtime_disabled_result()

    def _resolve_session(self, message: IncomingChatMessage) -> ConversationSession:
        if message.session_id:
            session = self.store.get_session(message.session_id)
            if session.owner_id != message.owner_id:
                raise ChatValidationError("Chat session does not belong to the message owner.")
            if session.channel != ChatChannel(message.channel):
                raise ChatValidationError("Chat session channel does not match the message channel.")
            if session.status == ConversationStatus.ARCHIVED:
                raise ChatValidationError("Archived chat sessions cannot receive new messages.")
            return session
        return self.store.get_or_create_session(
            channel=message.channel,
            external_conversation_id=message.conversation_id,
            owner_id=message.owner_id,
        )

    def _uses_agentic_runtime(self, message: IncomingChatMessage) -> bool:
        if self.runtime_mode != "agentic":
            return False
        text = (message.text or "").strip().lower()
        if self.debug_commands_enabled and (text == "/status" or text.startswith("/status ")):
            return False
        if self.debug_commands_enabled and (text == "/cancel" or text.startswith("/cancel ")):
            return False
        if self.agentic_runtime is None:
            raise ChatValidationError("Agentic runtime mode requires an AgenticRuntime.")
        return True

    def _runtime_disabled_result(self):
        reason = (
            self.runtime_unavailable_reason
            or "The chat runtime is running in deterministic mode."
        )
        return ChatToolResult(
            status=ChatResponseStatus.FAILED,
            primary_text=(
                "The AI conversation runtime is not enabled, so I cannot decide whether "
                "to answer, store, query, or correct this message."
            ),
            diagnostics=[
                ChatDiagnostic(
                    level=ChatDiagnosticLevel.ERROR,
                    code="ai_runtime_not_enabled",
                    message=reason,
                ),
            ],
            metadata={"operation": "chat_runtime", "runtime_mode": self.runtime_mode},
        )

    @traceable(name="Chat Runtime Call Agentic", run_type="chain")
    def _call_agentic(
        self,
        message: IncomingChatMessage,
        session_id: str,
        pending_context: PendingProcessContext | None,
        pending_contexts: list[PendingProcessContext],
        history_refs: list[str],
    ) -> ChatResponse:
        if self.agentic_runtime is None:
            raise ChatValidationError("Agentic runtime mode requires an AgenticRuntime.")
        conversation_context = self._agentic_conversation_context(
            message,
            session_id,
            pending_context,
            pending_contexts,
        )
        execution_context = AgenticToolExecutionContext(
            backend_facade=self.tool_facade,
            graph_service=self.graph_service,
            ingestion_service=self.ingestion_service,
            chat_store=self.store,
            session_id=session_id,
            channel=str(ChatChannel(message.channel)),
            conversation_id=message.conversation_id,
            owner_id=message.owner_id,
            sender_id=message.sender_id,
            message_id=message.message_id,
            current_text=(message.text or "").strip(),
            pending_process_context=pending_context,
            pending_process_contexts=pending_contexts,
            conversation_history_refs=history_refs,
            metadata={
                "media_refs": [media.model_dump(mode="json") for media in message.media_refs],
                **message.metadata,
            },
        )
        trace_context = (
            ai_flow_trace_session(
                session_id=session_id,
                message_id=message.message_id,
                current_text=(message.text or "").strip(),
                store=get_ai_flow_trace_store(),
            )
            if self.ai_flow_debug_enabled
            else nullcontext()
        )
        with trace_context:
            result = self.agentic_runtime.run(conversation_context, execution_context)
        return render_agentic_chat_response(result, session_id=session_id)

    def _agentic_conversation_context(
        self,
        message: IncomingChatMessage,
        session_id: str,
        pending_context: PendingProcessContext | None,
        pending_contexts: list[PendingProcessContext],
    ) -> AgenticConversationContext:
        text = (message.text or "").strip()
        agentic_pending_contexts = [
            context
            for context in (
                self._agentic_pending_context(pending) for pending in pending_contexts
            )
            if context is not None
        ]
        return self.history_service.build_conversation_context(
            current_text=text,
            history_records=self.store.list_messages(session_id, limit=100),
            current_time=message.received_at,
            timezone=str(message.metadata.get("timezone") or "UTC"),
            pending_process=self._agentic_pending_context(pending_context),
            pending_processes=agentic_pending_contexts,
            channel_metadata=ChannelSessionMetadata(
                channel=str(ChatChannel(message.channel)),
                conversation_id=message.conversation_id,
                owner_id=message.owner_id,
                session_id=session_id,
                sender_id=message.sender_id,
                message_id=message.message_id,
                received_at=message.received_at,
                metadata={
                    "reply_to_message_id": message.reply_to_message_id,
                    "media_count": len(message.media_refs),
                },
            ),
            metadata={"runtime_mode": "agentic"},
            fallback_current_text="Media message",
            exclude_record_ids={message.message_id},
        )

    def _agentic_pending_context(
        self,
        pending_context: PendingProcessContext | None,
    ) -> AgenticPendingProcessContext | None:
        if pending_context is None:
            return None
        process = pending_context.process_ref
        return AgenticPendingProcessContext(
            process_id=process.process_id,
            kind=str(process.kind),
            status=str(process.status),
            question=process.question,
            expires_at=process.expires_at,
            compact_summary=pending_context.context.get("summary"),
            unresolved_targets=list(pending_context.context.get("unresolved_targets") or []),
            metadata={
                key: value
                for key, value in process.metadata.items()
                if key
                in {
                    "reason",
                    "source",
                    "intent",
                    "decision",
                    "severity",
                    "resume_step",
                    "checkpoint_schema_version",
                }
            },
        )

    def _clarification_packet_from_pending(
        self,
        pending_context: PendingProcessContext,
    ) -> ClarificationPacket:
        packet = pending_context.context.get("clarification_packet")
        if not isinstance(packet, dict):
            packet = pending_context.process_ref.metadata.get("clarification_packet")
        if not isinstance(packet, dict):
            raise ChatValidationError(
                "The pending process does not contain a structured clarification packet.",
            )
        return ClarificationPacket.model_validate(packet)

    def _pending_process_contexts(self, session_id: str) -> list[PendingProcessContext]:
        if not hasattr(self.store, "list_pending_process_contexts"):
            active = self.store.get_active_pending_process_context(session_id)
            return [active] if active is not None else []
        return self.store.list_pending_process_contexts(
            session_id,
            statuses={PendingProcessStatus.PENDING, PendingProcessStatus.PAUSED},
            limit=5,
        )

    def _history_refs(self, session_id: str, explicit_refs: list[str]) -> list[str]:
        if explicit_refs:
            return list(explicit_refs)
        return [message.message_id for message in self.store.list_messages(session_id, limit=20)]

    def _pending_summary(self, source_text: str | None, question: str | None) -> str:
        source = (source_text or "a recent message").strip()
        if len(source) > 220:
            source = source[:217] + "..."
        if question:
            return f"Pending process for: {source}. Open question: {question}"
        return f"Pending process for: {source}."
