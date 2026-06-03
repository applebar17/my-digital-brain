import type { AnalyticsDistributionItem } from "../types";

interface DistributionBarsProps {
  items: AnalyticsDistributionItem[];
}

export function DistributionBars({ items }: DistributionBarsProps) {
  const maxValue = Math.max(...items.map((item) => item.value), 1);

  return (
    <div className="memory-distribution-bars">
      {items.map((item) => (
        <div className="memory-distribution-row" key={item.label}>
          <div>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
          <i>
            <b
              className={`bar-${item.tone ?? "primary"}`}
              style={{ width: `${Math.max((item.value / maxValue) * 100, 4)}%` }}
            />
          </i>
        </div>
      ))}
    </div>
  );
}
