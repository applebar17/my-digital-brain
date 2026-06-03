interface AnalyticsHeaderProps {
  serviceState: "not-connected" | "ready";
}

export function AnalyticsHeader({ serviceState }: AnalyticsHeaderProps) {
  return (
    <header className="memory-analytics-header">
      <div>
        <p className="eyebrow">Graph Health</p>
        <h2>Analytics</h2>
        <p>Static workspace shell for network volume, connectivity, and maintenance signals.</p>
      </div>
      <span className={`memory-analytics-state ${serviceState === "ready" ? "is-ready" : ""}`}>
        {serviceState === "ready" ? "Service Ready" : "Not Wired"}
      </span>
    </header>
  );
}
