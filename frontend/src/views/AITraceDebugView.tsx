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
  const [collapsedEvents, setCollapsedEvents] = useState<Set<number>>(() => new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => new Set());
  const [token] = useState(() => localStorage.getItem(tokenStorageKey) ?? defaultWebChatToken);

  const sortedEvents = useMemo(
    () => [...events].sort((left, right) => left.sequence - right.sequence),
    [events]
  );
  const allSectionKeys = useMemo(
    () =>
      sortedEvents.flatMap((event) =>
        event.sections.map((_, sectionIndex) => traceSectionKey(event.sequence, sectionIndex))
      ),
    [sortedEvents]
  );

  useEffect(() => {
    setEvents([]);
    setLatestSequence(0);
    setErrorMessage(undefined);
    setCollapsedEvents(new Set());
    setExpandedSections(new Set());
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
      setCollapsedEvents(new Set());
      setExpandedSections(new Set());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to clear traces.");
    }
  }

  function handleExpandAll() {
    setCollapsedEvents(new Set());
    setExpandedSections(new Set(allSectionKeys));
  }

  function handleCollapseAll() {
    setCollapsedEvents(new Set(sortedEvents.map((event) => event.sequence)));
    setExpandedSections(new Set());
  }

  function handleToggleEvent(sequence: number) {
    setCollapsedEvents((current) => toggleSetValue(current, sequence));
  }

  function handleToggleSection(sectionKey: string) {
    setExpandedSections((current) => toggleSetValue(current, sectionKey));
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
          <button type="button" disabled={sortedEvents.length === 0} onClick={handleExpandAll}>
            Expand all
          </button>
          <button type="button" disabled={sortedEvents.length === 0} onClick={handleCollapseAll}>
            Collapse all
          </button>
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
          sortedEvents.map((event) => (
            <TraceEventCard
              key={event.sequence}
              event={event}
              isCollapsed={collapsedEvents.has(event.sequence)}
              expandedSections={expandedSections}
              onToggleEvent={handleToggleEvent}
              onToggleSection={handleToggleSection}
            />
          ))
        )}
      </div>
    </section>
  );
}

interface TraceEventCardProps {
  event: AIFlowTraceEvent;
  isCollapsed: boolean;
  expandedSections: Set<string>;
  onToggleEvent: (sequence: number) => void;
  onToggleSection: (sectionKey: string) => void;
}

function TraceEventCard({
  event,
  isCollapsed,
  expandedSections,
  onToggleEvent,
  onToggleSection
}: TraceEventCardProps) {
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
  const articleClassName = [
    "ai-trace-event",
    event.status === "error" ? "is-error" : "",
    isCollapsed ? "is-collapsed" : ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={articleClassName}>
      <header>
        <button
          className="ai-trace-event-toggle"
          type="button"
          aria-expanded={!isCollapsed}
          onClick={() => onToggleEvent(event.sequence)}
        >
          <span className="ai-trace-disclosure" aria-hidden="true" />
          <span className="ai-trace-event-title">
            <strong>{event.title}</strong>
            <span>{meta.join(" / ")}</span>
          </span>
        </button>
        <div className="ai-trace-event-meta">
          <time>{new Date(event.timestamp).toLocaleTimeString()}</time>
          <span>{event.sections.length} sections</span>
        </div>
      </header>
      <div className="ai-trace-event-panel" aria-hidden={isCollapsed}>
        <div className="ai-trace-event-body">
          {event.sections.map((section, sectionIndex) => {
            const sectionKey = traceSectionKey(event.sequence, sectionIndex);
            const isSectionExpanded = expandedSections.has(sectionKey);
            return (
              <section
                className={`ai-trace-section ${
                  isSectionExpanded ? "is-expanded" : "is-collapsed"
                }`}
                key={sectionKey}
              >
                <header className="ai-trace-section-header">
                  <button
                    className="ai-trace-section-toggle"
                    type="button"
                    aria-expanded={isSectionExpanded}
                    onClick={() => onToggleSection(sectionKey)}
                  >
                    <span className="ai-trace-disclosure" aria-hidden="true" />
                    <span>{section.title}</span>
                  </button>
                  <span>{section.content_type}</span>
                </header>
                <div className="ai-trace-section-panel" aria-hidden={!isSectionExpanded}>
                  <div className="ai-trace-section-content">
                    <pre>{section.content || "(empty)"}</pre>
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </article>
  );
}

function traceSectionKey(eventSequence: number, sectionIndex: number): string {
  return `${eventSequence}:${sectionIndex}`;
}

function toggleSetValue<T>(current: Set<T>, value: T): Set<T> {
  const next = new Set(current);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  return next;
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
