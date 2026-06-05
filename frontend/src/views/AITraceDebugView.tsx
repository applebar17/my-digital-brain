import { useEffect, useMemo, useState } from "react";
import { clearAIFlowTraces, listAIFlowTraces } from "../api/aiTraces";
import { defaultWebChatToken } from "../config";
import type { AIFlowTraceEvent } from "../types/aiTrace";

const tokenStorageKey = "my-digital-brain.web-chat-token";

interface AITraceDebugViewProps {
  sessionId?: string;
}

export function AITraceDebugView({ sessionId }: AITraceDebugViewProps) {
  const [events, setEvents] = useState<AIFlowTraceEvent[]>([]);
  const [latestSequence, setLatestSequence] = useState(0);
  const [isPolling, setIsPolling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();
  const [token] = useState(() => localStorage.getItem(tokenStorageKey) ?? defaultWebChatToken);

  const sortedEvents = useMemo(
    () => [...events].sort((left, right) => left.sequence - right.sequence),
    [events]
  );

  useEffect(() => {
    setEvents([]);
    setLatestSequence(0);
    setErrorMessage(undefined);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      return undefined;
    }

    const activeSessionId = sessionId;
    let cancelled = false;

    async function poll() {
      setIsPolling(true);
      try {
        const result = await listAIFlowTraces(activeSessionId, token, {
          afterSequence: latestSequence,
          limit: 200
        });
        if (cancelled) {
          return;
        }
        if (result.events.length > 0) {
          setEvents((current) => appendUniqueEvents(current, result.events));
        }
        setLatestSequence(result.latest_sequence);
        setErrorMessage(undefined);
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load traces.");
        }
      } finally {
        if (!cancelled) {
          setIsPolling(false);
        }
      }
    }

    void poll();
    const intervalId = window.setInterval(poll, 1800);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [latestSequence, sessionId, token]);

  async function handleClear() {
    if (!sessionId) {
      return;
    }
    try {
      await clearAIFlowTraces(sessionId, token);
      setEvents([]);
      setLatestSequence(0);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to clear traces.");
    }
  }

  return (
    <section className="workspace ai-trace-workspace">
      <header className="ai-trace-header">
        <div>
          <p className="eyebrow">Debug Whiteboard</p>
          <h2>AI Flow Trace</h2>
          <p>
            {sessionId
              ? `Rendering trace events for chat session ${sessionId}.`
              : "Open a chat session trace from the chat header."}
          </p>
        </div>
        <div className="ai-trace-header-actions">
          <span>{isPolling ? "Polling" : "Idle"}</span>
          <button type="button" disabled={!sessionId} onClick={handleClear}>
            Clear
          </button>
        </div>
      </header>

      {errorMessage ? <div className="ai-trace-error">{errorMessage}</div> : null}

      <div className="ai-trace-board" aria-live="polite">
        {!sessionId ? (
          <div className="ai-trace-empty">No session selected.</div>
        ) : sortedEvents.length === 0 ? (
          <div className="ai-trace-empty">No trace events recorded yet.</div>
        ) : (
          sortedEvents.map((event) => <TraceEventCard key={event.sequence} event={event} />)
        )}
      </div>
    </section>
  );
}

function TraceEventCard({ event }: { event: AIFlowTraceEvent }) {
  const meta = [
    `#${event.sequence}`,
    event.call_kind,
    event.status,
    event.state_id,
    event.purpose,
    event.model,
    event.schema_id,
    event.toolbox_name
  ].filter(Boolean);

  return (
    <article className={`ai-trace-event ${event.status === "error" ? "is-error" : ""}`}>
      <header>
        <div>
          <strong>{event.title}</strong>
          <p>{meta.join(" / ")}</p>
        </div>
        <time>{new Date(event.timestamp).toLocaleTimeString()}</time>
      </header>
      {event.sections.map((section) => (
        <section className="ai-trace-section" key={`${event.sequence}-${section.title}`}>
          <h3>{section.title}</h3>
          <pre>{section.content || "(empty)"}</pre>
        </section>
      ))}
    </article>
  );
}

function appendUniqueEvents(
  current: AIFlowTraceEvent[],
  nextEvents: AIFlowTraceEvent[]
): AIFlowTraceEvent[] {
  const bySequence = new Map<number, AIFlowTraceEvent>();
  current.forEach((event) => bySequence.set(event.sequence, event));
  nextEvents.forEach((event) => bySequence.set(event.sequence, event));
  return [...bySequence.values()].sort((left, right) => left.sequence - right.sequence);
}
