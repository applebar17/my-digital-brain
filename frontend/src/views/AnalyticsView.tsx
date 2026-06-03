import { AnalyticsCard } from "../features/analytics/components/AnalyticsCard";
import { AnalyticsHeader } from "../features/analytics/components/AnalyticsHeader";
import { DistributionBars } from "../features/analytics/components/DistributionBars";
import { IntegrityPanel } from "../features/analytics/components/IntegrityPanel";
import { MetricStrip } from "../features/analytics/components/MetricStrip";
import { PendingProcessesPanel } from "../features/analytics/components/PendingProcessesPanel";
import { RankedNodeList } from "../features/analytics/components/RankedNodeList";
import type {
  AnalyticsDistributionItem,
  AnalyticsMetric,
  AnalyticsRankedItem,
  PendingProcessItem
} from "../features/analytics/types";

const metrics: AnalyticsMetric[] = [
  {
    label: "Nodes",
    value: "0",
    detail: "Awaiting analytics service",
    tone: "accent"
  },
  {
    label: "Edges",
    value: "0",
    detail: "Awaiting analytics service"
  },
  {
    label: "Contradictions",
    value: "0",
    detail: "No live review source",
    tone: "warning"
  },
  {
    label: "Pending",
    value: "0",
    detail: "Pending-process feed not wired"
  }
];

const nodeDistribution: AnalyticsDistributionItem[] = [
  { label: "Person", value: 0, tone: "primary" },
  { label: "Event", value: 0, tone: "secondary" },
  { label: "Place", value: 0, tone: "muted" },
  { label: "Topic", value: 0, tone: "muted" }
];

const relationshipDistribution: AnalyticsDistributionItem[] = [
  { label: "MENTIONED_IN", value: 0, tone: "primary" },
  { label: "PARTICIPATED_IN", value: 0, tone: "secondary" },
  { label: "RELATED_TO", value: 0, tone: "muted" },
  { label: "SUPPORTED_BY", value: 0, tone: "muted" }
];

const centralNodes: AnalyticsRankedItem[] = [
  {
    id: "placeholder-person",
    title: "No central nodes yet",
    subtitle: "Connect analytics summary service to populate this list",
    count: 0
  }
];

const pendingProcesses: PendingProcessItem[] = [];

export function AnalyticsView() {
  return (
    <div className="workspace analytics-workspace memory-analytics-workspace">
      <AnalyticsHeader serviceState="not-connected" />
      <MetricStrip metrics={metrics} />

      <div className="memory-analytics-grid">
        <AnalyticsCard title="Nodes By Label" eyebrow="Network Composition">
          <DistributionBars items={nodeDistribution} />
        </AnalyticsCard>

        <AnalyticsCard title="Edges By Type" eyebrow="Relationship Shape">
          <DistributionBars items={relationshipDistribution} />
        </AnalyticsCard>

        <AnalyticsCard title="Central Nodes" eyebrow="Connectivity">
          <RankedNodeList items={centralNodes} />
        </AnalyticsCard>

        <AnalyticsCard title="Integrity" eyebrow="Maintenance">
          <IntegrityPanel contradictions={0} staleItems={0} orphanedRefs={0} />
        </AnalyticsCard>

        <AnalyticsCard title="Pending Processes" eyebrow="Runtime">
          <PendingProcessesPanel items={pendingProcesses} />
        </AnalyticsCard>
      </div>
    </div>
  );
}
