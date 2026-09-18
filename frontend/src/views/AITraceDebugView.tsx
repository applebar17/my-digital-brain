import { useEffect, useMemo, useState } from "react";
import { clearAIFlowTraces, listAIFlowTraces } from "../api/aiTraces";
import { listChatSessions } from "../api/chat";
import { defaultOwnerId, defaultWebChatToken } from "../config";
import type { AIFlowTraceEvent } from "../types/aiTrace";
import type { ConversationSessionSummary } from "../types/chat";

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
  const [sessions, setSessions] = useState<ConversationSessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [showRawEvents, setShowRawEvents] = useState(false);
  const [token] = useState(() => localStorage.getItem(tokenStorageKey) ?? defaultWebChatToken);

  const sortedEvents = useMemo(
    () => [...events].sort((left, right) => left.sequence - right.sequence),
    [events]
  );
  const failureCount = useMemo(
    () => sortedEvents.filter(isTraceFailure).length,
    [sortedEvents]
  );
  const visibleEvents = useMemo(
    () =>
      sortedEvents.filter(
        (event) => showRawEvents || isWorkflowEvent(event) || isTraceFailure(event)
      ),
    [showRawEvents, sortedEvents]
  );
  const allSectionKeys = useMemo(
    () =>
      sortedEvents.flatMap((event) =>
        event.sections.map((_, sectionIndex) => traceSectionKey(event.sequence, sectionIndex))
      ),
    [sortedEvents]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      setIsLoadingSessions(true);
      try {
        const result = await listChatSessions(defaultOwnerId, token, {
          channel: "web",
          limit: 100
        });
        if (!cancelled) {
          setSessions(result.sessions);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load chat sessions.");
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSessions(false);
        }
      }
    }

    void loadSessions();
    return () => {
      cancelled = true;
    };
  }, [token]);

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
          const newestSequence = Math.max(...result.events.map((event) => event.sequence));
          setCollapsedEvents((current) => {
            const next = new Set(current);
            result.events.forEach((event) => {
              if (event.sequence === newestSequence || isTraceFailure(event)) {
                next.delete(event.sequence);
              } else {
                next.add(event.sequence);
              }
            });
            return next;
          });
          setExpandedSections((current) => {
            const next = new Set(current);
            result.events.forEach((event) => {
              if (!isTraceFailure(event)) {
                return;
              }
              event.sections.forEach((section, sectionIndex) => {
                if (section.title.includes("ERROR") || sectionHasFailure(section.content)) {
                  next.add(traceSectionKey(event.sequence, sectionIndex));
                }
              });
            });
            return next;
          });
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

  function handleSessionChange(nextSessionId: string) {
    window.location.hash = nextSessionId ? `debug/${nextSessionId}` : "debug";
  }

  const selectedSession = sessions.find((session) => session.session_id === sessionId);

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
              ? `Inspecting ${selectedSession?.title ?? "selected chat"}.`
              : "Select a chat session to inspect its AI runtime trace."}
          </p>
        </div>
        <div className="ai-trace-header-actions">
          <span>{isPolling ? "Polling" : "Idle"}</span>
          <span className={failureCount > 0 ? "ai-trace-failure-count" : ""}>
            {failureCount > 0 ? `${failureCount} failure${failureCount === 1 ? "" : "s"}` : "No failures"}
          </span>
          <button type="button" onClick={() => setShowRawEvents((current) => !current)}>
            {showRawEvents ? "Hide raw events" : `Show raw events (${sortedEvents.length - visibleEvents.length})`}
          </button>
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

      <section className="ai-trace-session-picker" aria-label="Trace session selection">
        <div>
          <p className="eyebrow">Developer tool</p>
          <strong>Conversation trace</strong>
          <span>
            {sessions.length > 0
              ? `${sessions.length} recent web chat${sessions.length === 1 ? "" : "s"}`
              : "Choose a chat to load its recorded events."}
          </span>
        </div>
        <label>
          <span>Chat session</span>
          <select
            value={sessionId ?? ""}
            disabled={isLoadingSessions}
            onChange={(event) => handleSessionChange(event.target.value)}
          >
            <option value="">Select a chat session...</option>
            {sessionId && !selectedSession ? (
              <option value={sessionId}>Selected session ({shortId(sessionId)})</option>
            ) : null}
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.title} · {session.status} · {shortId(session.session_id)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="ai-trace-session-refresh"
          disabled={isLoadingSessions}
          onClick={() => window.location.reload()}
        >
          Refresh chats
        </button>
      </section>

      {errorMessage ? <div className="ai-trace-error">{errorMessage}</div> : null}

      <div className="ai-trace-board" aria-live="polite">
        {!sessionId ? (
          <div className="ai-trace-empty">No session selected.</div>
        ) : sortedEvents.length === 0 ? (
          <div className="ai-trace-empty">No trace events recorded yet.</div>
        ) : (
          visibleEvents.map((event) => (
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
    isTraceFailure(event) ? "is-error" : "",
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
            <em>{traceSummary(event)}</em>
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

function traceSummary(event: AIFlowTraceEvent): string {
  if (isTraceFailure(event)) {
    return failureReason(event) ?? "This runtime step failed. The error details are open below.";
  }
  if (event.call_kind.includes("tool")) {
    return event.toolbox_name
      ? `Tool step: ${event.toolbox_name} completed.`
      : "A backend tool step completed.";
  }
  if (event.call_kind.includes("payload")) {
    return "Prepared the model request and its available actions.";
  }
  if (event.call_kind.includes("response") || event.call_kind.includes("result")) {
    return "Received and normalized the model result.";
  }
  if (event.call_kind.includes("embedding")) {
    return "Generated vector representations for retrieval.";
  }
  return `Recorded ${humanize(event.call_kind)}.`;
}

function isWorkflowEvent(event: AIFlowTraceEvent): boolean {
  return event.call_kind === "agentic_state_input" ||
    event.call_kind === "agentic_state_output" ||
    event.call_kind === "agentic_structured_state_input" ||
    event.call_kind === "agentic_structured_state_output" ||
    event.call_kind === "backend_process_result";
}

function isTraceFailure(event: AIFlowTraceEvent): boolean {
  return ["error", "failed", "blocked"].includes(event.status.toLowerCase()) ||
    event.sections.some((section) => sectionHasFailure(section.content));
}

function sectionHasFailure(content: string): boolean {
  return /"(?:status|level)"\s*:\s*"(?:error|failed|blocked)"|"error"\s*:/i.test(content);
}

function failureReason(event: AIFlowTraceEvent): string | undefined {
  const diagnostic = event.sections.find((section) =>
    section.title.includes("ERROR") || sectionHasFailure(section.content)
  );
  if (!diagnostic) {
    return undefined;
  }
  const match = diagnostic.content.match(/"(?:message|error)"\s*:\s*"([^"]+)"/i);
  return match?.[1];
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(value: string): string {
  return value.slice(0, 8);
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
