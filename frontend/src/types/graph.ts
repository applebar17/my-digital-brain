export interface NodeSearchResult {
  label: string;
  labels: string[];
  properties: Record<string, unknown>;
}

export interface RelationshipResult {
  type: string;
  from_id: string;
  to_id: string;
  properties: Record<string, unknown>;
}

export interface TimelineItem {
  id: string;
  label: string;
  title?: string | null;
  description?: string | null;
  time_value?: string | null;
  time_basis?: string | null;
  time_precision?: string | null;
  source_ids: string[];
  emotional_summary?: string | null;
  original_user_words?: string | null;
}

export interface TimelineResult {
  seed: NodeSearchResult;
  items: TimelineItem[];
}

export interface EntityDetailResult {
  target: NodeSearchResult;
  canonical?: NodeSearchResult | null;
  relationships: RelationshipResult[];
  perceptions: NodeSearchResult[];
  relationship_contexts: NodeSearchResult[];
  sources: NodeSearchResult[];
  changes: NodeSearchResult[];
  contradictions: NodeSearchResult[];
  merges: NodeSearchResult[];
}

export interface MemoryLogDetailResult {
  memory_log: NodeSearchResult;
  hosts: NodeSearchResult[];
  involved: NodeSearchResult[];
  relationship_contexts: NodeSearchResult[];
  media_assets: NodeSearchResult[];
  relationships: RelationshipResult[];
}

export interface GraphViewNode {
  id: string;
  label: string;
  title?: string | null;
  description?: string | null;
  lifecycle_state?: string | null;
  privacy_level?: string | null;
  trust_level?: string | null;
  emotional_summary?: string | null;
  temporal_summary?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  display_metadata: Record<string, unknown>;
}

export interface GraphViewRelationship {
  id: string;
  type: string;
  from_id: string;
  to_id: string;
  description?: string | null;
  lifecycle_state?: string | null;
  emotional_summary?: string | null;
  temporal_summary?: string | null;
}

export interface GraphViewResult {
  seed_id: string;
  nodes: GraphViewNode[];
  relationships: GraphViewRelationship[];
}

export interface MapViewResult {
  seed_id?: string | null;
  places: GraphViewNode[];
  events: GraphViewNode[];
  relationships: GraphViewRelationship[];
  timeline: TimelineItem[];
}

export interface GraphAnalyticsItem {
  key: string;
  count: number;
  label?: string | null;
}

export interface GraphAnalyticsSummary {
  node_counts: Record<string, number>;
  relationship_counts: Record<string, number>;
  top_connected_nodes: GraphAnalyticsItem[];
  top_emotion_tags: GraphAnalyticsItem[];
  unresolved_contradictions: number;
}

export type GraphSearchMode = "property" | "semantic" | "hybrid";

export interface SemanticSearchTraceEvent {
  stage: string;
  status: string;
  message: string;
  data: Record<string, unknown>;
}

export type VectorScopeName = "memory_node_summaries" | "memory_contexts" | "memory_micro_logs";
export type HitRole = "domain_node" | "context" | "memory_log";

export interface SemanticMemoryHit {
  rank: number;
  score: number;
  source: "semantic" | "property";
  vector_id?: string | null;
  distance?: number | null;
  collection: string;
  scope?: VectorScopeName | null;
  hit_role?: HitRole | null;
  embedding_scope?: string | null;
  matched_target_id?: string | null;
  matched_target_label?: string | null;
  matched_target?: GraphViewNode | null;
  display_target_id?: string | null;
  display_target_label?: string | null;
  primary_target_id: string;
  primary_target_label: string;
  canonical_target_id?: string | null;
  related_target_ids: string[];
  source_ids: string[];
  relationship_ids: string[];
  raw_score?: number | null;
  normalized_score?: number | null;
  scope_weight?: number | null;
  hydration_path: string[];
  matched_records: Record<string, unknown>[];
  title?: string | null;
  description?: string | null;
  document_preview?: string | null;
  target?: GraphViewNode | null;
  canonical_target?: GraphViewNode | null;
  debug: Record<string, unknown>;
}

export interface GraphContextPackage {
  target: Record<string, unknown>;
  current_facts: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  relationship_contexts: Record<string, unknown>[];
  perceptions: Record<string, unknown>[];
  matched_records: Record<string, unknown>[];
  timeline: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  notes: string[];
  alias_map: Record<string, string>;
}

export interface SemanticMemorySearchResult {
  query: string;
  mode: "semantic" | "hybrid";
  collection: string;
  hits: SemanticMemoryHit[];
  graph_view: GraphViewResult;
  context_packages: GraphContextPackage[];
  trace: SemanticSearchTraceEvent[];
}
