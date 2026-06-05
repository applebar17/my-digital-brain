from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from my_digital_brain.api.routes.chat import require_web_chat_auth
from my_digital_brain.config import Settings, get_settings
from my_digital_brain.debug import AIFlowTraceEventList, get_ai_flow_trace_store

router = APIRouter(prefix="/debug", tags=["debug"])


def require_ai_flow_debug_enabled(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.ai_flow_debug_enabled:
        raise HTTPException(status_code=404, detail="AI flow debugging is not enabled.")


@router.get(
    "/ai-traces/sessions/{session_id}",
    response_model=AIFlowTraceEventList,
    dependencies=[
        Depends(require_ai_flow_debug_enabled),
        Depends(require_web_chat_auth),
    ],
)
def list_ai_flow_traces(
    session_id: str,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> AIFlowTraceEventList:
    return get_ai_flow_trace_store().list(
        session_id,
        after_sequence=after_sequence,
        limit=limit,
    )


@router.delete(
    "/ai-traces/sessions/{session_id}",
    status_code=204,
    dependencies=[
        Depends(require_ai_flow_debug_enabled),
        Depends(require_web_chat_auth),
    ],
)
def clear_ai_flow_traces(session_id: str) -> Response:
    get_ai_flow_trace_store().clear(session_id)
    return Response(status_code=204)
