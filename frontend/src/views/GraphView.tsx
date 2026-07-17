import { useState } from "react";
import type { FormEvent } from "react";
import {
  getEntityDetail,
  getMapView,
  getMemoryLogDetail,
  getMemoryLogsForNode,
  getNeighborhoodView,
  getNodeRelationships,
  hybridSearch,
  getTimelineForNode,
  searchNodes,
  semanticSearch
} from "../api/graph";
import type { MemoryLogFilters } from "../api/graph";
import { GraphContextBar } from "../features/graph/components/GraphContextBar";
import { GraphInspectorPanel } from "../features/graph/components/GraphInspectorPanel";
import { GraphSearchWindow } from "../features/graph/components/GraphSearchWindow";
import { GraphTimelineDock } from "../features/graph/components/GraphTimelineDock";
import { MemoryGraphCanvas } from "../features/graph/components/MemoryGraphCanvas";
import type {
  EntityDetailResult,
  GraphSearchMode,
  GraphViewNode,
  GraphViewRelationship,
  GraphViewResult,
  MapViewResult,
  MemoryLogDetailResult,
  NodeSearchResult,
  RelationshipResult,
  SemanticMemoryHit,
  SemanticMemorySearchResult,
  TimelineResult
} from "../types/graph";
import { firstString, nodeId, nodeTitle } from "../lib/graphLabels";

export function GraphView() {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<GraphSearchMode>("hybrid");
  const [label, setLabel] = useState("");
  const [depth, setDepth] = useState(1);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showDatabaseSample, setShowDatabaseSample] = useState(false);
  const [databaseSampleLimit, setDatabaseSampleLimit] = useState(25);
  const [results, setResults] = useState<NodeSearchResult[]>([]);
  const [retrievalResult, setRetrievalResult] = useState<SemanticMemorySearchResult>();
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [detail, setDetail] = useState<EntityDetailResult>();
  const [graph, setGraph] = useState<GraphViewResult>();
  const [timeline, setTimeline] = useState<TimelineResult>();
  const [mapView, setMapView] = useState<MapViewResult>();
  const [memoryLogs, setMemoryLogs] = useState<NodeSearchResult[]>([]);
  const [memoryLogFilters, setMemoryLogFilters] = useState<MemoryLogFilters>(DEFAULT_MEMORY_LOG_FILTERS);
  const [selectedMemoryLogId, setSelectedMemoryLogId] = useState<string>();
  const [selectedMemoryLogDetail, setSelectedMemoryLogDetail] = useState<MemoryLogDetailResult>();
  const [isLoading, setIsLoading] = useState(false);
  const [isMemoryLogLoading, setIsMemoryLogLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>();
  const [errorMessage, setErrorMessage] = useState<string>();
  const selectedHit = selectedNodeId
    ? findHitForDisplayTarget(retrievalResult?.hits ?? [], selectedNodeId)
    : undefined;

  async function handleSearch(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setSelectedNodeId(undefined);
    setDetail(undefined);
    setTimeline(undefined);
    setMapView(undefined);
    setMemoryLogs([]);
    setSelectedMemoryLogId(undefined);
    setSelectedMemoryLogDetail(undefined);
    setRetrievalResult(undefined);
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage(
      searchMode === "property" ? "Searching graph..." : "Retrieving graph memories..."
    );
    try {
      const trimmedQuery = query.trim();
      if (searchMode === "property") {
        const found = await searchNodes({
          query: trimmedQuery || undefined,
          label: label || undefined,
          limit: 25
        });
        setResults(found);
        setGraph(undefined);
        setStatusMessage(`${found.length} result${found.length === 1 ? "" : "s"} found`);
        return;
      }
      if (!trimmedQuery) {
        throw new Error("Semantic and hybrid search require a text query.");
      }
      const found =
        searchMode === "semantic"
          ? await semanticSearch({
              query: trimmedQuery,
              include_archived: includeArchived,
              include_history: true,
              limit: 25
            })
          : await hybridSearch({
              query: trimmedQuery,
              label: label || undefined,
              include_archived: includeArchived,
              include_history: true,
              limit: 25
            });
      setResults([]);
      setRetrievalResult(found);
      setGraph(found.graph_view);
      setStatusMessage(
        `${found.hits.length} retrieval hit${found.hits.length === 1 ? "" : "s"} found`
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to search graph.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadDatabaseSample(
    nextLimit = databaseSampleLimit,
    nextLabel = label,
    nextIncludeArchived = includeArchived
  ) {
    const boundedLimit = Math.max(1, Math.min(nextLimit, 100));
    setDatabaseSampleLimit(boundedLimit);
    setSelectedNodeId(undefined);
    setDetail(undefined);
    setTimeline(undefined);
    setMapView(undefined);
    setMemoryLogs([]);
    setSelectedMemoryLogId(undefined);
    setSelectedMemoryLogDetail(undefined);
    setRetrievalResult(undefined);
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Loading database sample...");
    try {
      const nodes = await searchNodes({
        label: nextLabel || undefined,
        lifecycle_state: nextIncludeArchived ? undefined : "active",
        limit: boundedLimit
      });
      const nodeIds = new Set(nodes.map(nodeId).filter(Boolean));
      const relationshipBatches = await Promise.all(
        nodes.map((node) => {
          const id = nodeId(node);
          return id ? getNodeRelationships(id, undefined, "both", 100) : Promise.resolve([]);
        })
      );
      const relationships = dedupeRelationships(relationshipBatches.flat()).filter(
        (relationship) => nodeIds.has(relationship.from_id) && nodeIds.has(relationship.to_id)
      );
      setResults(nodes);
      setGraph(toDatabaseSampleGraph(nodes, relationships));
      setStatusMessage(
        `Database sample loaded: ${nodes.length} node${nodes.length === 1 ? "" : "s"}, ` +
          `${relationships.length} visible edge${relationships.length === 1 ? "" : "s"}`
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load database sample.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadNodeContext(id: string, nextIncludeArchived = includeArchived) {
    if (!id) {
      return;
    }
    setSelectedNodeId(id);
    setDetail(undefined);
    setMemoryLogs([]);
    setSelectedMemoryLogId(undefined);
    setSelectedMemoryLogDetail(undefined);
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Loading graph context...");
    try {
      const [nextDetail, nextTimeline, nextMapView, nextMemoryLogs] = await Promise.all([
        getEntityDetail(id, true, nextIncludeArchived, 50),
        getTimelineForNode(id, undefined, undefined, true, 100),
        getMapView(id, undefined, undefined, undefined, undefined, 100),
        getMemoryLogsForNode(id, {
          ...memoryLogFilters,
          include_archived: nextIncludeArchived || memoryLogFilters.include_archived
        })
      ]);
      setDetail(nextDetail);
      setTimeline(nextTimeline);
      setMapView(nextMapView);
      setMemoryLogs(nextMemoryLogs);
      setStatusMessage("Graph context loaded");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load graph context.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  function handleDepthChange(nextDepth: number) {
    const boundedDepth = Math.max(1, Math.min(nextDepth, 3));
    setDepth(boundedDepth);
  }

  function handleLabelChange(nextLabel: string) {
    setLabel(nextLabel);
    if (showDatabaseSample && !selectedNodeId) {
      void loadDatabaseSample(databaseSampleLimit, nextLabel, includeArchived);
    }
  }

  function handleIncludeArchivedChange(nextIncludeArchived: boolean) {
    setIncludeArchived(nextIncludeArchived);
    if (selectedNodeId) {
      void loadNodeContext(selectedNodeId, nextIncludeArchived);
    } else if (showDatabaseSample) {
      void loadDatabaseSample(databaseSampleLimit, label, nextIncludeArchived);
    }
  }

  function handleShowDatabaseSampleChange(nextShowDatabaseSample: boolean) {
    setShowDatabaseSample(nextShowDatabaseSample);
    if (nextShowDatabaseSample) {
      void loadDatabaseSample(databaseSampleLimit);
      return;
    }
    setGraph(undefined);
    setResults([]);
    setRetrievalResult(undefined);
    setSelectedNodeId(undefined);
    setDetail(undefined);
    setTimeline(undefined);
    setMapView(undefined);
    setMemoryLogs([]);
    setSelectedMemoryLogId(undefined);
    setSelectedMemoryLogDetail(undefined);
    setStatusMessage(undefined);
    setErrorMessage(undefined);
  }

  function handleCloseInspector() {
    setSelectedNodeId(undefined);
    setDetail(undefined);
    setTimeline(undefined);
    setMapView(undefined);
    setMemoryLogs([]);
    setSelectedMemoryLogId(undefined);
    setSelectedMemoryLogDetail(undefined);
  }

  function handleDatabaseSampleLimitChange(nextLimit: number) {
    const boundedLimit = Math.max(1, Math.min(Number.isFinite(nextLimit) ? nextLimit : 25, 100));
    setDatabaseSampleLimit(boundedLimit);
    if (showDatabaseSample) {
      void loadDatabaseSample(boundedLimit);
    }
  }

  async function focusSelectedNeighborhood() {
    if (!selectedNodeId) {
      return;
    }
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Focusing selected node neighborhood...");
    try {
      const nextGraph = await getNeighborhoodView(selectedNodeId, depth, true, includeArchived, 100);
      setGraph(nextGraph);
      setStatusMessage("Focused graph neighborhood loaded");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to focus graph neighborhood.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  async function reloadMemoryLogs(nextFilters = memoryLogFilters) {
    if (!selectedNodeId) {
      return;
    }
    setIsMemoryLogLoading(true);
    setErrorMessage(undefined);
    try {
      const logs = await getMemoryLogsForNode(selectedNodeId, nextFilters);
      setMemoryLogs(logs);
      setSelectedMemoryLogId(undefined);
      setSelectedMemoryLogDetail(undefined);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load MemoryLog timeline.");
    } finally {
      setIsMemoryLogLoading(false);
    }
  }

  function handleMemoryLogFiltersChange(nextFilters: MemoryLogFilters) {
    const normalizedFilters = normalizeMemoryLogFilters(nextFilters);
    setMemoryLogFilters(normalizedFilters);
    void reloadMemoryLogs(normalizedFilters);
  }

  function handleResetMemoryLogFilters() {
    setMemoryLogFilters(DEFAULT_MEMORY_LOG_FILTERS);
    void reloadMemoryLogs(DEFAULT_MEMORY_LOG_FILTERS);
  }

  async function handleSelectMemoryLog(logId: string) {
    setSelectedMemoryLogId(logId);
    setSelectedMemoryLogDetail(undefined);
    setIsMemoryLogLoading(true);
    setErrorMessage(undefined);
    try {
      setSelectedMemoryLogDetail(await getMemoryLogDetail(logId));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load MemoryLog detail.");
    } finally {
      setIsMemoryLogLoading(false);
    }
  }

  return (
    <div className="workspace graph-workspace memory-graph-workspace">
      <GraphContextBar
        query={query}
        searchMode={searchMode}
        label={label}
        depth={depth}
        includeArchived={includeArchived}
        showDatabaseSample={showDatabaseSample}
        databaseSampleLimit={databaseSampleLimit}
        isLoading={isLoading}
        statusMessage={statusMessage}
        errorMessage={errorMessage}
        onQueryChange={setQuery}
        onSearchModeChange={setSearchMode}
        onLabelChange={handleLabelChange}
        onDepthChange={handleDepthChange}
        onIncludeArchivedChange={handleIncludeArchivedChange}
        onShowDatabaseSampleChange={handleShowDatabaseSampleChange}
        onDatabaseSampleLimitChange={handleDatabaseSampleLimitChange}
        onSearch={handleSearch}
      />

      <div className="memory-graph-layout">
        <div className="memory-graph-stage">
          <MemoryGraphCanvas
            graph={graph}
            selectedNodeId={selectedNodeId}
            isLoading={isLoading}
            onSelectNode={(id) => void loadNodeContext(id)}
            onClearSelection={handleCloseInspector}
          />
          <GraphTimelineDock timeline={timeline} mapView={mapView} />
        </div>

        <div className="memory-graph-side-pane">
          <GraphSearchWindow
            searchMode={searchMode}
            results={results}
            retrievalResult={retrievalResult}
            selectedNodeId={selectedNodeId}
            onSelectNode={(id) => void loadNodeContext(id)}
          />
          <GraphInspectorPanel
            detail={detail}
            selectedNodeId={selectedNodeId}
            selectedHit={selectedHit}
            retrievalResult={retrievalResult}
            memoryLogs={memoryLogs}
            memoryLogFilters={memoryLogFilters}
            selectedMemoryLogId={selectedMemoryLogId}
            selectedMemoryLogDetail={selectedMemoryLogDetail}
            isMemoryLogLoading={isMemoryLogLoading}
            onClose={handleCloseInspector}
            onFocusNeighborhood={() => void focusSelectedNeighborhood()}
            onMemoryLogFiltersChange={handleMemoryLogFiltersChange}
            onResetMemoryLogFilters={handleResetMemoryLogFilters}
            onSelectMemoryLog={(logId) => void handleSelectMemoryLog(logId)}
          />
        </div>
      </div>
    </div>
  );
}

const DEFAULT_MEMORY_LOG_FILTERS: MemoryLogFilters = {
  include_archived: false,
  limit: 50
};

function normalizeMemoryLogFilters(filters: MemoryLogFilters): MemoryLogFilters {
  return {
    from_time: filters.from_time || undefined,
    to_time: filters.to_time || undefined,
    log_kind: filters.log_kind || undefined,
    source_kind: filters.source_kind || undefined,
    involved_target_id: filters.involved_target_id || undefined,
    media_only: Boolean(filters.media_only),
    include_archived: Boolean(filters.include_archived),
    limit: Math.max(1, Math.min(filters.limit ?? 50, 200))
  };
}

function findHitForDisplayTarget(
  hits: SemanticMemoryHit[],
  targetId: string
): SemanticMemoryHit | undefined {
  return hits.find((hit) => (
    hit.display_target_id
    || hit.canonical_target_id
    || hit.primary_target_id
  ) === targetId);
}

function toDatabaseSampleGraph(
  nodes: NodeSearchResult[],
  relationships: RelationshipResult[]
): GraphViewResult | undefined {
  if (nodes.length === 0) {
    return undefined;
  }
  return {
    seed_id: nodeId(nodes[0]),
    nodes: nodes.map(toGraphViewNode),
    relationships: relationships.map(toGraphViewRelationship)
  };
}

function toGraphViewNode(node: NodeSearchResult): GraphViewNode {
  const properties = node.properties;
  return {
    id: nodeId(node),
    label: node.label,
    title: nodeTitle(node),
    description: stringValue(properties.description),
    lifecycle_state: stringValue(properties.lifecycle_state),
    privacy_level: stringValue(properties.privacy_level),
    trust_level: stringValue(properties.trust_level),
    emotional_summary: stringValue(properties.emotional_summary),
    temporal_summary: optionalFirstString(
      properties.resolved_start,
      properties.valid_from,
      properties.source_time,
      properties.observed_at
    ),
    latitude: numberValue(properties.latitude),
    longitude: numberValue(properties.longitude),
    display_metadata: {}
  };
}

function toGraphViewRelationship(relationship: RelationshipResult): GraphViewRelationship {
  const properties = relationship.properties;
  return {
    id: stringValue(properties.id) || `${relationship.from_id}:${relationship.type}:${relationship.to_id}`,
    type: relationship.type,
    from_id: relationship.from_id,
    to_id: relationship.to_id,
    description: stringValue(properties.description),
    lifecycle_state: stringValue(properties.lifecycle_state),
    emotional_summary: stringValue(properties.emotional_summary),
    temporal_summary: optionalFirstString(
      properties.resolved_start,
      properties.valid_from,
      properties.source_time,
      properties.observed_at
    )
  };
}

function dedupeRelationships(relationships: RelationshipResult[]): RelationshipResult[] {
  const seen = new Set<string>();
  const deduped: RelationshipResult[] = [];
  relationships.forEach((relationship) => {
    const id = stringValue(relationship.properties.id);
    const key = id || `${relationship.from_id}:${relationship.type}:${relationship.to_id}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    deduped.push(relationship);
  });
  return deduped;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function optionalFirstString(...values: unknown[]): string | null {
  const value = firstString(...values);
  return value === "Untitled" ? null : value;
}
