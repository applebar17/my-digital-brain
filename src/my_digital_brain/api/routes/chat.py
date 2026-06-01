from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from my_digital_brain.api.routes.graph import get_graph_service
from my_digital_brain.chat.exceptions import ChatNotFoundError, ChatValidationError
from my_digital_brain.chat.models import (
    ChatResponse,
    ConversationSessionDetail,
)
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.chat.tool_facade import MemoryBackendToolFacade
from my_digital_brain.chat.web import WebChatAdapter, WebChatMessageRequest
from my_digital_brain.config import Settings, get_settings
from my_digital_brain.graph.service import GraphService

router = APIRouter(prefix="/chat", tags=["chat"])
security = HTTPBearer(auto_error=False)

_chat_store = InMemoryChatSessionStore()
_web_adapter = WebChatAdapter()


class CancelChatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_id: str
    reason: str | None = None


def get_chat_runtime(
    graph_service: GraphService = Depends(get_graph_service),
) -> ChatRuntime:
    return ChatRuntime(
        store=_chat_store,
        tool_facade=MemoryBackendToolFacade(graph_service=graph_service),
    )


def require_web_chat_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> None:
    expected_token = settings.web_chat_auth_token
    if expected_token is None:
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing web chat bearer token.")
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=403, detail="Invalid web chat bearer token.")


def chat_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ChatValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ChatNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/messages",
    response_model=ChatResponse,
    dependencies=[Depends(require_web_chat_auth)],
)
def post_chat_message(
    message: WebChatMessageRequest,
    runtime: ChatRuntime = Depends(get_chat_runtime),
) -> ChatResponse:
    try:
        return runtime.handle_message(_web_adapter.normalize(message))
    except Exception as exc:
        raise chat_http_error(exc) from exc


@router.get(
    "/sessions/{session_id}",
    response_model=ConversationSessionDetail,
    dependencies=[Depends(require_web_chat_auth)],
)
def get_chat_session(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    runtime: ChatRuntime = Depends(get_chat_runtime),
) -> ConversationSessionDetail:
    try:
        return runtime.get_session_detail(session_id, limit=limit)
    except Exception as exc:
        raise chat_http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=ChatResponse,
    dependencies=[Depends(require_web_chat_auth)],
)
def cancel_chat_session_process(
    session_id: str,
    request: CancelChatSessionRequest,
    runtime: ChatRuntime = Depends(get_chat_runtime),
) -> ChatResponse:
    try:
        return runtime.cancel_session_process(
            session_id,
            owner_id=request.owner_id,
            reason=request.reason,
        )
    except Exception as exc:
        raise chat_http_error(exc) from exc
