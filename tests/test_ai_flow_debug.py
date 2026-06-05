from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.api.routes import chat as chat_routes
from my_digital_brain.api.routes import debug as debug_routes
from my_digital_brain.config import Settings
from my_digital_brain.debug import (
    AIFlowTraceSection,
    AIFlowTraceStore,
    ai_flow_trace_call,
    ai_flow_trace_session,
    record_ai_flow_event,
    record_openai_payload,
)


def test_ai_flow_trace_store_appends_lists_and_clears() -> None:
    store = AIFlowTraceStore(max_events_per_session=2)
    with ai_flow_trace_session(
        session_id="session-1",
        message_id="message-1",
        current_text="hello",
        store=store,
    ):
        record_ai_flow_event(
            title="First",
            call_kind="test",
            sections=[AIFlowTraceSection(title="LLM OUTPUT", content="one")],
        )
        record_ai_flow_event(
            title="Second",
            call_kind="test",
            sections=[AIFlowTraceSection(title="LLM OUTPUT", content="two")],
        )
        record_ai_flow_event(
            title="Third",
            call_kind="test",
            sections=[AIFlowTraceSection(title="LLM OUTPUT", content="three")],
        )

    listed = store.list("session-1")
    assert listed.latest_sequence == 3
    assert [event.title for event in listed.events] == ["Second", "Third"]

    cursor = store.list("session-1", after_sequence=2)
    assert [event.title for event in cursor.events] == ["Third"]

    store.clear("session-1")
    assert store.list("session-1").events == []


def test_openai_payload_trace_records_state_metadata_and_redacts_secret_keys() -> None:
    store = AIFlowTraceStore()
    with ai_flow_trace_session(
        session_id="session-2",
        message_id="message-2",
        current_text="remember Marco",
        store=store,
    ):
        with ai_flow_trace_call(
            call_kind="chat_with_tools",
            title="conversation_entry",
            state_id="conversation_entry",
            purpose="conversation_entry",
            model="gpt-test",
            provider="fake",
            prompt_id="conversation_entry",
            toolbox_name="agentic:conversation_entry",
        ):
            record_openai_payload(
                {
                    "model": "gpt-test",
                    "messages": [
                        {"role": "system", "content": "System prompt"},
                        {
                            "role": "user",
                            "content": {"api_key": "secret", "text": "hello"},
                        },
                    ],
                    "tools": [],
                },
            )

    event = store.list("session-2").events[0]
    assert event.state_id == "conversation_entry"
    assert event.model == "gpt-test"
    assert event.toolbox_name == "agentic:conversation_entry"
    assert "System prompt" in event.sections[0].content
    assert "secret" not in event.sections[1].content
    assert "[REDACTED]" in event.sections[1].content


def test_debug_trace_endpoint_is_gated_and_lists_session_events() -> None:
    app = FastAPI()
    app.include_router(debug_routes.router)
    settings = Settings(
        _env_file=None,
        AI_FLOW_DEBUG_ENABLED=True,
        WEB_CHAT_AUTH_TOKEN="debug-token",
    )
    debug_routes.get_ai_flow_trace_store().clear("session-api")
    app.dependency_overrides[debug_routes.get_settings] = lambda: settings
    app.dependency_overrides[chat_routes.get_settings] = lambda: settings

    with ai_flow_trace_session(
        session_id="session-api",
        message_id="message-api",
        current_text="hello",
        store=debug_routes.get_ai_flow_trace_store(),
    ):
        record_ai_flow_event(
            title="API Event",
            call_kind="test",
            sections=[AIFlowTraceSection(title="LLM OUTPUT", content="ok")],
        )

    client = TestClient(app)
    response = client.get(
        "/debug/ai-traces/sessions/session-api",
        headers={"Authorization": "Bearer debug-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["events"][0]["title"] == "API Event"

    clear_response = client.delete(
        "/debug/ai-traces/sessions/session-api",
        headers={"Authorization": "Bearer debug-token"},
    )
    assert clear_response.status_code == 204
    assert debug_routes.get_ai_flow_trace_store().list("session-api").events == []


def test_debug_trace_endpoint_returns_404_when_disabled() -> None:
    app = FastAPI()
    app.include_router(debug_routes.router)
    settings = Settings(
        _env_file=None,
        AI_FLOW_DEBUG_ENABLED=False,
        WEB_CHAT_AUTH_TOKEN="debug-token",
    )
    app.dependency_overrides[debug_routes.get_settings] = lambda: settings
    app.dependency_overrides[chat_routes.get_settings] = lambda: settings

    client = TestClient(app)
    response = client.get(
        "/debug/ai-traces/sessions/session-api",
        headers={"Authorization": "Bearer debug-token"},
    )
    assert response.status_code == 404
