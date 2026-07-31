export interface AnalyticsMetric {
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "accent" | "warning" | "danger";
}

export interface AnalyticsDistributionItem {
  label: string;
  value: number;
  tone?: "primary" | "secondary" | "muted" | "danger";
}

export interface AnalyticsRankedItem {
  id: string;
  title: string;
  subtitle: string;
  count: number;
}
