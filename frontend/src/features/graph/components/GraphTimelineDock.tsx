import { EmptyState } from "../../../components/EmptyState";
import type { MapViewResult, TimelineResult } from "../../../types/graph";

interface GraphTimelineDockProps {
  timeline?: TimelineResult;
  mapView?: MapViewResult;
}

export function GraphTimelineDock({ timeline, mapView }: GraphTimelineDockProps) {
  const items = timeline?.items ?? [];
  const places = mapView?.places.length ?? 0;
  const events = mapView?.events.length ?? 0;

  return (
    <section className="memory-dock">
      <header className="memory-dock-tabs">
        <button className="is-active" type="button">Timeline</button>
        <button type="button">Map Context</button>
        <div className="memory-dock-summary">
          <span>{places} places</span>
          <span>{events} events</span>
        </div>
      </header>

      {items.length === 0 ? (
        <div className="memory-dock-empty">
          <EmptyState title="No timeline yet" body="Time-linked memories will appear when the selected node has events." />
        </div>
      ) : (
        <div className="memory-timeline-rail">
          {items.slice(0, 6).map((item, index) => {
            const rawTime = item.time_value ?? item.time_basis ?? "Unknown";
            return (
              <article className={`memory-timeline-node ${index === 0 ? "is-active" : ""}`} key={item.id}>
                <span title={rawTime}>
                  {compactTimelineTime(item.time_value, item.time_precision, item.time_basis)}
                </span>
                <i />
                <strong>{item.title ?? item.label}</strong>
                {item.description && <p>{item.description}</p>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function compactTimelineTime(
  value?: string | null,
  precision?: string | null,
  fallback?: string | null
): string {
  const text = value?.trim() || fallback?.trim();
  if (!text) {
    return "Unknown";
  }

  const rangeParts = splitRange(text);
  if (rangeParts) {
    return rangeParts
      .map((part) => compactTimelineTime(part, precision))
      .join(" - ");
  }

  const match = text.match(/^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(?:[T\s](\d{2}):(\d{2}))?/);
  if (!match) {
    return text;
  }

  const [, year, month, day, hour, minute] = match;
  if (precision === "year" || !month) {
    return year;
  }
  const monthLabel = monthNames[Math.max(0, Math.min(Number(month) - 1, 11))];
  if (precision === "month" || !day) {
    return `${monthLabel} ${year}`;
  }

  const dayLabel = String(Number(day));
  const timeLabel = hour && minute && `${hour}:${minute}` !== "00:00" ? ` ${hour}:${minute}` : "";
  return `${dayLabel} ${monthLabel} ${year}${timeLabel}`;
}

function splitRange(value: string): [string, string] | null {
  if (value.includes("/")) {
    const [start, end] = value.split("/", 2).map((part) => part.trim());
    return start && end ? [start, end] : null;
  }
  const separator = " to ";
  if (value.includes(separator)) {
    const [start, end] = value.split(separator, 2).map((part) => part.trim());
    return start && end ? [start, end] : null;
  }
  return null;
}

const monthNames = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec"
];
