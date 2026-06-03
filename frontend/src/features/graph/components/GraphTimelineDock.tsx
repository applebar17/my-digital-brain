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
          {items.slice(0, 6).map((item, index) => (
            <article className={`memory-timeline-node ${index === 0 ? "is-active" : ""}`} key={item.id}>
              <span>{item.time_value ?? item.time_basis ?? "Unknown"}</span>
              <i />
              <strong>{item.title ?? item.label}</strong>
              {item.description && <p>{item.description}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
