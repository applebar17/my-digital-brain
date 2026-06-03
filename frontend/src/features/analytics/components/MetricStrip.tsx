import type { AnalyticsMetric } from "../types";

interface MetricStripProps {
  metrics: AnalyticsMetric[];
}

export function MetricStrip({ metrics }: MetricStripProps) {
  return (
    <section className="memory-metric-strip" aria-label="Graph summary metrics">
      {metrics.map((metric) => (
        <article className={`memory-analytics-metric metric-${metric.tone ?? "neutral"}`} key={metric.label}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          <p>{metric.detail}</p>
        </article>
      ))}
    </section>
  );
}
