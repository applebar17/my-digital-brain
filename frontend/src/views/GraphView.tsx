import { useState } from "react";
import type { FormEvent } from "react";
import {
  getEntityDetail,
  getMapView,
  getNeighborhoodView,
  getNodeRelationships,
  hybridSearch,
  getTimelineForNode,
  searchNodes,
  semanticSearch
} from "../api/graph";
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
  NodeSearchResult,
  RelationshipResult,
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
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>();
  const [errorMessage, setErrorMessage] = useState<string>();

  async function handleSearch(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setSelectedNodeId(undefined);
    setDetail(undefined);
    setTimeline(undefined);
    setMapView(undefined);
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

  async function loadNodeContext(id: string, nextDepth = depth, nextIncludeArchived = includeArchived) {
    if (!id) {
      return;
    }
    setSelectedNodeId(id);
    setDetail(undefined);
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Loading graph context...");
    try {
      const [nextDetail, nextGraph, nextTimeline, nextMapView] = await Promise.all([
        getEntityDetail(id, true, nextIncludeArchived, 50),
        getNeighborhoodView(id, nextDepth, true, nextIncludeArchived, 100),
        getTimelineForNode(id, undefined, undefined, true, 100),
        getMapView(id, undefined, undefined, undefined, undefined, 100)
      ]);
      setDetail(nextDetail);
      setGraph(nextGraph);
      setTimeline(nextTimeline);
      setMapView(nextMapView);
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
    if (selectedNodeId) {
      void loadNodeContext(selectedNodeId, boundedDepth, includeArchived);
    }
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
      void loadNodeContext(selectedNodeId, depth, nextIncludeArchived);
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
    setStatusMessage(undefined);
    setErrorMessage(undefined);
  }

  function handleCloseInspector() {
    setSelectedNodeId(undefined);
    setTimeline(undefined);
    setMapView(undefined);
  }

  function handleDatabaseSampleLimitChange(nextLimit: number) {
    const boundedLimit = Math.max(1, Math.min(Number.isFinite(nextLimit) ? nextLimit : 25, 100));
    setDatabaseSampleLimit(boundedLimit);
    if (showDatabaseSample) {
      void loadDatabaseSample(boundedLimit);
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
            onClose={handleCloseInspector}
          />
        </div>
      </div>
    </div>
  );
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
