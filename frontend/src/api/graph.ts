import { apiRequest } from "./http";
import type {
  EntityDetailResult,
  GraphAnalyticsSummary,
  GraphViewResult,
  MapViewResult,
  NodeSearchResult,
  RelationshipResult,
  SemanticMemorySearchResult,
  TimelineResult
} from "../types/graph";

export interface SearchNodesParams {
  label?: string;
  query?: string;
  lifecycle_state?: string;
  privacy_level?: string;
  trust_level?: string;
  limit?: number;
}

export function searchNodes(params: SearchNodesParams): Promise<NodeSearchResult[]> {
  return apiRequest<NodeSearchResult[]>("/graph/nodes/search", {
    query: {
      label: params.label,
      query: params.query,
      lifecycle_state: params.lifecycle_state,
      privacy_level: params.privacy_level,
      trust_level: params.trust_level,
      limit: params.limit
    }
  });
}

export function getNodeRelationships(
  nodeId: string,
  relationshipType?: string,
  direction = "both",
  limit = 50
): Promise<RelationshipResult[]> {
  return apiRequest<RelationshipResult[]>(`/graph/nodes/${nodeId}/relationships`, {
    query: {
      relationship_type: relationshipType,
      direction,
      limit
    }
  });
}

export function getEntityDetail(
  nodeId: string,
  includeHistory = false,
  includeArchived = false,
  limit = 50
): Promise<EntityDetailResult> {
  return apiRequest<EntityDetailResult>(`/graph/nodes/${nodeId}/detail`, {
    query: { include_history: includeHistory, include_archived: includeArchived, limit }
  });
}

export function getNeighborhoodView(
  seedId: string,
  depth = 1,
  includeHistory = false,
  includeArchived = false,
  limit = 100
): Promise<GraphViewResult> {
  return apiRequest<GraphViewResult>("/graph/views/neighborhood", {
    query: {
      seed_id: seedId,
      depth,
      include_history: includeHistory,
      include_archived: includeArchived,
      limit
    }
  });
}

export function getTimelineForNode(
  nodeId: string,
  fromTime?: string,
  toTime?: string,
  includeHistory = false,
  limit = 100
): Promise<TimelineResult> {
  return apiRequest<TimelineResult>(`/graph/nodes/${nodeId}/timeline`, {
    query: {
      from_time: fromTime,
      to_time: toTime,
      include_history: includeHistory,
      limit
    }
  });
}

export function getMapView(
  seedId?: string,
  city?: string,
  country?: string,
  fromTime?: string,
  toTime?: string,
  limit = 100
): Promise<MapViewResult> {
  return apiRequest<MapViewResult>("/graph/views/map", {
    query: {
      seed_id: seedId,
      city,
      country,
      from_time: fromTime,
      to_time: toTime,
      limit
    }
  });
}

export function getAnalyticsSummary(
  includeArchived = false,
  limit = 20
): Promise<GraphAnalyticsSummary> {
  return apiRequest<GraphAnalyticsSummary>("/graph/analytics/summary", {
    query: { include_archived: includeArchived, limit }
  });
}

export interface SemanticSearchParams {
  query: string;
  include_archived?: boolean;
  include_history?: boolean;
  limit?: number;
}

export interface HybridSearchParams extends SemanticSearchParams {
  label?: string;
}

export function semanticSearch(params: SemanticSearchParams): Promise<SemanticMemorySearchResult> {
  return apiRequest<SemanticMemorySearchResult>("/graph/search/semantic", {
    query: {
      query: params.query,
      include_archived: params.include_archived,
      include_history: params.include_history,
      limit: params.limit
    }
  });
}

export function hybridSearch(params: HybridSearchParams): Promise<SemanticMemorySearchResult> {
  return apiRequest<SemanticMemorySearchResult>("/graph/search/hybrid", {
    query: {
      query: params.query,
      label: params.label,
      include_archived: params.include_archived,
      include_history: params.include_history,
      limit: params.limit
    }
  });
}
