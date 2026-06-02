from __future__ import annotations

from typing import Literal

from my_digital_brain.agentic.contexts import (
    ChannelSessionMetadata,
    ConversationContext as AgenticConversationContext,
    PendingProcessContext as AgenticPendingProcessContext,
)
from my_digital_brain.agentic.history import AgenticHistoryService
from my_digital_brain.agentic.runtime import AgenticRuntime
from my_digital_brain.agentic.tools import AgenticToolExecutionContext
from my_digital_brain.chat.agentic_renderer import render_agentic_chat_response
from my_digital_brain.chat.enums import (
    ChatChannel,
    ChatResponseStatus,
    ConversationMessageRole,
)
from my_digital_brain.chat.exceptions import ChatValidationError
from my_digital_brain.chat.facade import (
    BackendToolFacade,
    CancelPendingProcessRequest,
    ChatToolRequest,
    NoopBackendToolFacade,
)
from my_digital_brain.chat.models import (
    ChatResponse,
    ConversationMessage,
    ConversationSessionDetail,
    IncomingChatMessage,
    PendingProcessContext,
)
from my_digital_brain.chat.store import ChatSessionStore, InMemoryChatSessionStore


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
    ) -> None:
        self.store = store or InMemoryChatSessionStore()
        self.tool_facade = tool_facade or NoopBackendToolFacade()
        self.runtime_mode = runtime_mode
        self.agentic_runtime = agentic_runtime
        self.graph_service = graph_service
        self.ingestion_service = ingestion_service
        self.history_service = history_service or AgenticHistoryService()

    def handle_message(self, message: IncomingChatMessage) -> ChatResponse:
        if not (message.text and message.text.strip()) and not message.media_refs:
            raise ChatValidationError("Incoming chat message must include text or media.")

        session = self.store.get_or_create_session(
            channel=message.channel,
            external_conversation_id=message.conversation_id,
            owner_id=message.owner_id,
        )

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
        history_refs = self._history_refs(
            session.session_id,
            explicit_refs=message.conversation_history_refs,
        )
        if self._uses_agentic_runtime(message):
            response = self._call_agentic(
                message,
                session.session_id,
                pending_context,
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
                actions=result.actions,
                evidence=result.evidence,
                diagnostics=result.diagnostics,
                metadata=result.metadata,
            )

        if response.pending_process is not None:
            self.store.save_pending_process_context(
                session.session_id,
                PendingProcessContext(
                    process_ref=response.pending_process,
                    conversation_history_refs=history_refs,
                    context={
                        "source_message_id": message.message_id,
                        "source_text": message.text,
                    },
                ),
            )
        elif response.metadata.get("clear_pending_process"):
            self.store.clear_active_pending_process(session.session_id)

        self.store.append_message(
            ConversationMessage(
                session_id=session.session_id,
                role=ConversationMessageRole.ASSISTANT,
                text=response.primary_text,
                pending_process_id=(
                    response.pending_process.process_id if response.pending_process else None
                ),
                metadata={
                    "response_id": response.response_id,
                    "status": response.status,
                },
            ),
        )
        return response

    def get_session_detail(self, session_id: str, limit: int = 50) -> ConversationSessionDetail:
        return self.store.get_session_detail(session_id, limit=limit)

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

        if lower_text == "/status" or lower_text.startswith("/status "):
            return self.tool_facade.get_conversation_status(request)
        if lower_text == "/cancel" or lower_text.startswith("/cancel "):
            result = self.tool_facade.cancel_pending_process(
                CancelPendingProcessRequest(
                    session_id=session_id,
                    pending_process_id=(
                        pending_context.process_ref.process_id if pending_context else None
                    ),
                    owner_id=message.owner_id,
                    reason=text[7:].strip() if len(text) > 7 else None,
                ),
            )
            return result.model_copy(
                update={"metadata": {**result.metadata, "clear_pending_process": True}},
                deep=True,
            )
        if lower_text.startswith("/ask"):
            return self.tool_facade.query_memory_context(
                request.model_copy(update={"text": text[4:].strip() or text}, deep=True),
            )
        if lower_text.startswith("/correct"):
            return self.tool_facade.propose_memory_correction(
                request.model_copy(update={"text": text[8:].strip() or text}, deep=True),
            )

        if not text and message.media_refs:
            return self.tool_facade.start_memory_ingestion(
                request.model_copy(
                    update={"metadata": {**request.metadata, "media_only": True}},
                    deep=True,
                ),
            )
        return self.tool_facade.start_memory_ingestion(request)

    def _uses_agentic_runtime(self, message: IncomingChatMessage) -> bool:
        if self.runtime_mode != "agentic":
            return False
        text = (message.text or "").strip().lower()
        if text == "/status" or text.startswith("/status "):
            return False
        if text == "/cancel" or text.startswith("/cancel "):
            return False
        if self.agentic_runtime is None:
            raise ChatValidationError("Agentic runtime mode requires an AgenticRuntime.")
        return True

    def _call_agentic(
        self,
        message: IncomingChatMessage,
        session_id: str,
        pending_context: PendingProcessContext | None,
        history_refs: list[str],
    ) -> ChatResponse:
        if self.agentic_runtime is None:
            raise ChatValidationError("Agentic runtime mode requires an AgenticRuntime.")
        conversation_context = self._agentic_conversation_context(
            message,
            session_id,
            pending_context,
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
            conversation_history_refs=history_refs,
            metadata={
                "media_refs": [media.model_dump(mode="json") for media in message.media_refs],
                **message.metadata,
            },
        )
        result = self.agentic_runtime.run(conversation_context, execution_context)
        return render_agentic_chat_response(result, session_id=session_id)

    def _agentic_conversation_context(
        self,
        message: IncomingChatMessage,
        session_id: str,
        pending_context: PendingProcessContext | None,
    ) -> AgenticConversationContext:
        text = (message.text or "").strip()
        return self.history_service.build_conversation_context(
            current_text=text,
            history_records=self.store.list_messages(session_id, limit=100),
            current_time=message.received_at,
            timezone=str(message.metadata.get("timezone") or "UTC"),
            pending_process=self._agentic_pending_context(pending_context),
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
            metadata={
                **process.metadata,
                "context": pending_context.context,
                "conversation_history_refs": pending_context.conversation_history_refs,
            },
        )

    def _history_refs(self, session_id: str, explicit_refs: list[str]) -> list[str]:
        if explicit_refs:
            return list(explicit_refs)
        return [message.message_id for message in self.store.list_messages(session_id, limit=20)]
