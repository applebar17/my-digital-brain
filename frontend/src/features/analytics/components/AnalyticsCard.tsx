import type { ReactNode } from "react";

interface AnalyticsCardProps {
  title: string;
  eyebrow: string;
  children: ReactNode;
}

export function AnalyticsCard({ title, eyebrow, children }: AnalyticsCardProps) {
  return (
    <section className="memory-analytics-card">
      <header>
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3>{title}</h3>
        </div>
      </header>
      {children}
    </section>
  );
}
