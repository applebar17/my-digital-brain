import type { AnalyticsRankedItem } from "../types";

interface RankedNodeListProps {
  items: AnalyticsRankedItem[];
}

export function RankedNodeList({ items }: RankedNodeListProps) {
  return (
    <div className="memory-ranked-list">
      {items.map((item) => (
        <article className="memory-ranked-row" key={item.id}>
          <div className="memory-ranked-icon">{initials(item.title)}</div>
          <div>
            <strong>{item.title}</strong>
            <span>{item.subtitle}</span>
          </div>
          <b>{item.count}</b>
        </article>
      ))}
    </div>
  );
}

function initials(value: string): string {
  return value
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
