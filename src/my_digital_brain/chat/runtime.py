from __future__ import annotations

from contextlib import nullcontext
from my_digital_brain.agentic.contexts import (
    ChannelSessionMetadata,
    ConversationContext as AgenticConversationContext,
)
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime import AgenticRuntime
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.chat.agentic_renderer import render_agentic_chat_response
from my_digital_brain.chat.clarification import (
    answer_packet_from_progress,
    merge_clarification_progress,
    render_clarification_questions,
    resolved_clarifications_from_answers,
    summarize_clarification_answers,
    validate_clarification_answers,
)
from my_digital_brain.chat.enums import (
    ChatChannel,
    ChatDiagnosticLevel,
    ChatResponseStatus,
    ConversationStatus,
    ConversationMessageRole,
)
from my_digital_brain.chat.exceptions import ChatValidationError
from my_digital_brain.chat.models import (
    ChatResponse,
    ChatDiagnostic,
    ConversationMessage,
    ConversationSession,
    ConversationSessionList,
    ConversationSessionDetail,
    ClarificationAnswer,
    ClarificationAnswerPacket,
    IncomingChatMessage,
)
from my_digital_brain.chat.store import ChatSessionStore, InMemoryChatSessionStore
from my_digital_brain.debug import ai_flow_trace_session, get_ai_flow_trace_store
from my_digital_brain.core.owner_context import OwnerSnapshot


class ChatRuntime:
    def __init__(
        self,
        store: ChatSessionStore | None = None,
        *,
        agentic_runtime: AgenticRuntime | None = None,
        graph_service: object | None = None,
        ingestion_service: object | None = None,
        semantic_search_service: object | None = None,
        vectorization_service: object | None = None,
        history_service: AgenticHistoryService | None = None,
        debug_commands_enabled: bool = False,
        ai_flow_debug_enabled: bool = False,
        owner_snapshot: OwnerSnapshot | None = None,
    ) -> None:
        self.store = store or InMemoryChatSessionStore()
        if agentic_runtime is None:
            raise ChatValidationError("ChatRuntime requires an AgenticRuntime.")
        self.agentic_runtime = agentic_runtime
        self.graph_service = graph_service
        self.ingestion_service = ingestion_service
        self.semantic_search_service = semantic_search_service
        self.vectorization_service = vectorization_service
        self.history_service = history_service or AgenticHistoryService()
        self.debug_commands_enabled = debug_commands_enabled
        self.ai_flow_debug_enabled = ai_flow_debug_enabled
        self.owner_snapshot = owner_snapshot

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
                metadata={
                    "sender_id": message.sender_id,
                    "reply_to_message_id": message.reply_to_message_id,
                    "received_at": message.received_at.isoformat(),
                    **message.metadata,
                },
            ),
        )

        history_refs = self._history_refs(
            session.session_id,
            explicit_refs=message.conversation_history_refs,
        )
        response = self._call_agentic(
            message,
            session.session_id,
            history_refs,
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
        self.store.append_message(
            ConversationMessage(
                session_id=session_id,
                role=ConversationMessageRole.ASSISTANT,
                text=self._assistant_history_text(response),
                metadata={
                    "response_id": response.response_id,
                    "status": response.status,
                    **(
                        {
                            "ui_hidden": True,
                            "message_kind": "clarification_prompt",
                        }
                        if response.clarification_packet is not None
                        else {}
                    ),
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
        if session.owner_id != owner_id:
            raise ChatValidationError("Chat session does not belong to the request owner.")
        response = ChatResponse(
            session_id=session.session_id,
            status=ChatResponseStatus.FAILED,
            primary_text=(
                "Legacy process cancellation is no longer available. "
                "Active clarification must be answered through its agentic frame."
            ),
            diagnostics=[
                ChatDiagnostic(
                    level=ChatDiagnosticLevel.ERROR,
                    code="legacy_process_cancel_removed",
                    message="Legacy process cancellation is not part of the agentic runtime.",
                    details={"reason": reason},
                )
            ],
            metadata={"operation": "cancel_session_process", "legacy_path_removed": True},
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
        if self.agentic_runtime is None:
            raise ChatValidationError("Clarification continuation requires an AgenticRuntime.")
        session = self.store.get_session(session_id)
        if session.owner_id != owner_id:
            raise ChatValidationError("Chat session does not belong to the request owner.")
        if not hasattr(self.store, "get_agentic_frame"):
            raise ChatValidationError("The chat store does not support agentic frames.")
        frame = self.store.get_agentic_frame(answer_packet.frame_id)
        if frame.session_id != session.session_id:
            raise ChatValidationError("Clarification answers must target this chat session.")
        if frame.status != "interrupted":
            raise ChatValidationError("Clarification frame is not waiting for user input.")
        if frame.clarification_packet is None:
            raise ChatValidationError("The agentic frame has no active clarification packet.")
        packet = frame.clarification_packet
        validate_clarification_answers(packet, answer_packet)
        progress = merge_clarification_progress(
            packet,
            frame.metadata.get("clarification_progress"),
            answer_packet,
        )
        partial_answer_summary = summarize_clarification_answers(packet, answer_packet)
        partial_resolved_clarifications = resolved_clarifications_from_answers(packet, answer_packet)

        self.store.append_message(
            ConversationMessage(
                session_id=session.session_id,
                channel_message_id=message_id,
                role=ConversationMessageRole.USER,
                text=partial_answer_summary,
                metadata={
                    "sender_id": sender_id,
                    "ui_hidden": True,
                    "message_kind": "clarification_answer",
                    "agentic_frame_id": frame.frame_id,
                    "tool_call_id": answer_packet.tool_call_id,
                    "clarification_answer_packet": answer_packet.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "clarification_answer_summary": partial_answer_summary,
                },
            ),
        )
        frame = self.store.update_agentic_frame_status(
            session.session_id,
            frame.frame_id,
            "interrupted",
            metadata={
                "clarification_progress": progress,
                "resolved_clarifications": [
                    *list(frame.metadata.get("resolved_clarifications") or []),
                    *partial_resolved_clarifications,
                ],
            },
            clarification_packet=packet.model_dump(mode="json", exclude_none=True),
        )
        if not progress["is_complete"]:
            response = ChatResponse(
                session_id=session.session_id,
                status=ChatResponseStatus.AWAITING_CLARIFICATION,
                primary_text="Clarification answer received.",
                clarification_packet=packet,
                metadata={
                    "operation": "answer_clarification",
                    "resumed_frame_id": frame.frame_id,
                    "clarification_progress": progress,
                },
            )
            self._persist_response(
                session.session_id,
                response,
                source_message_id=message_id,
                source_text=partial_answer_summary,
                history_refs=self._history_refs(session.session_id, []),
            )
            return response

        complete_answer_packet = answer_packet_from_progress(packet, progress)
        validate_clarification_answers(packet, complete_answer_packet)
        answer_summary = summarize_clarification_answers(packet, complete_answer_packet)
        resolved_clarifications = resolved_clarifications_from_answers(packet, complete_answer_packet)
        execution_context = AgenticToolExecutionContext(
            graph_service=self.graph_service,
            ingestion_service=self.ingestion_service,
            semantic_search_service=self.semantic_search_service,
            vectorization_service=self.vectorization_service,
            chat_store=self.store,
            session_id=session.session_id,
            channel=str(session.channel),
            conversation_id=session.external_conversation_id,
            owner_id=owner_id,
            owner_snapshot=self.owner_snapshot,
            sender_id=sender_id,
            message_id=message_id,
            current_text=answer_summary,
            conversation_history_refs=self._history_refs(session.session_id, []),
            metadata={
                "clarification_answer_packet": answer_packet.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "complete_clarification_answer_packet": complete_answer_packet.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "clarification_answer_summary": answer_summary,
                "resolved_clarifications": resolved_clarifications,
            },
            frame_id=frame.frame_id,
            parent_frame_id=frame.parent_frame_id,
            parent_tool_call_id=frame.parent_tool_call_id,
        )
        result = self.agentic_runtime.resume_frame(
            frame,
            execution_context,
            clarification_answer_summary=answer_summary,
            answer_packet=complete_answer_packet,
            resolved_clarifications=resolved_clarifications,
        )
        response = render_agentic_chat_response(result, session_id=session.session_id)
        response = response.model_copy(
            update={
                "metadata": {
                    **response.metadata,
                    "operation": "answer_clarification",
                    "resumed_frame_id": frame.frame_id,
                }
            },
            deep=True,
        )
        self._persist_response(
            session.session_id,
            response,
            source_message_id=message_id,
            source_text=answer_summary,
            history_refs=self._history_refs(session.session_id, []),
        )
        return response


    def active_clarification_frame_for_message(
        self,
        message: IncomingChatMessage,
    ):
        session = self._resolve_session(message)
        frame = self.store.get_active_agentic_frame(session.session_id)
        if frame is None or frame.clarification_packet is None:
            return session, None
        return session, frame

    def answer_active_clarification(
        self,
        message: IncomingChatMessage,
        *,
        selected_option_id: str | None = None,
        free_text: str | None = None,
        expected_frame_id: str | None = None,
        expected_question_id: str | None = None,
    ) -> ChatResponse:
        session, frame = self.active_clarification_frame_for_message(message)
        if frame is None or frame.clarification_packet is None:
            raise ChatValidationError("There is no active clarification for this chat.")
        if expected_frame_id is not None and frame.frame_id != expected_frame_id:
            raise ChatValidationError("Telegram clarification answer targeted a different frame.")
        packet = frame.clarification_packet
        question = _current_clarification_question(
            packet,
            frame.metadata.get("clarification_progress"),
        )
        if expected_question_id is not None and question.question_id != expected_question_id:
            raise ChatValidationError("Telegram clarification answer targeted a different question.")
        answer = ClarificationAnswer(
            question_id=question.question_id,
            selected_option_ids=[selected_option_id] if selected_option_id else [],
            free_text=(free_text or None),
        )
        answer_packet = ClarificationAnswerPacket(
            packet_id=packet.packet_id,
            frame_id=frame.frame_id,
            tool_call_id=packet.tool_call_id or "",
            answers=[answer],
        )
        return self.answer_clarification(
            session.session_id,
            owner_id=session.owner_id,
            sender_id=message.sender_id,
            message_id=message.message_id,
            answer_packet=answer_packet,
        )

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

    @traceable(name="Chat Runtime Call Agentic", run_type="chain")
    def _call_agentic(
        self,
        message: IncomingChatMessage,
        session_id: str,
        history_refs: list[str],
    ) -> ChatResponse:
        conversation_context = self._agentic_conversation_context(
            message,
            session_id,
        )
        execution_context = AgenticToolExecutionContext(
            graph_service=self.graph_service,
            ingestion_service=self.ingestion_service,
            semantic_search_service=self.semantic_search_service,
            vectorization_service=self.vectorization_service,
            chat_store=self.store,
            session_id=session_id,
            channel=str(ChatChannel(message.channel)),
            conversation_id=message.conversation_id,
            owner_id=message.owner_id,
            owner_snapshot=self.owner_snapshot,
            sender_id=message.sender_id,
            message_id=message.message_id,
            current_text=(message.text or "").strip(),
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
    ) -> AgenticConversationContext:
        text = (message.text or "").strip()
        return self.history_service.build_conversation_context(
            current_text=text,
            history_records=self.store.list_messages(session_id, limit=100),
            current_time=message.received_at,
            timezone=str(message.metadata.get("timezone") or "UTC"),
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

    def _history_refs(self, session_id: str, explicit_refs: list[str]) -> list[str]:
        if explicit_refs:
            return list(explicit_refs)
        return [message.message_id for message in self.store.list_messages(session_id, limit=20)]


def _current_clarification_question(packet, progress: dict | None):
    answered = set()
    if isinstance(progress, dict):
        answered = set(progress.get("answered_question_ids") or [])
        current_question_id = progress.get("current_question_id")
        if current_question_id:
            for question in packet.questions:
                if question.question_id == current_question_id:
                    return question
    for question in packet.questions:
        if question.question_id not in answered:
            return question
    return packet.questions[-1]
