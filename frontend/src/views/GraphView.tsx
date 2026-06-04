import { useState } from "react";
import type { FormEvent } from "react";
import {
  getEntityDetail,
  getMapView,
  getNeighborhoodView,
  getTimelineForNode,
  searchNodes
} from "../api/graph";
import { GraphContextBar } from "../features/graph/components/GraphContextBar";
import { GraphInspectorPanel } from "../features/graph/components/GraphInspectorPanel";
import { GraphSearchWindow } from "../features/graph/components/GraphSearchWindow";
import { GraphTimelineDock } from "../features/graph/components/GraphTimelineDock";
import { MemoryGraphCanvas } from "../features/graph/components/MemoryGraphCanvas";
import type {
  EntityDetailResult,
  GraphViewResult,
  MapViewResult,
  NodeSearchResult,
  TimelineResult
} from "../types/graph";

export function GraphView() {
  const [query, setQuery] = useState("");
  const [label, setLabel] = useState("");
  const [depth, setDepth] = useState(1);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [results, setResults] = useState<NodeSearchResult[]>([]);
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
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Searching graph...");
    try {
      const found = await searchNodes({
        query: query.trim() || undefined,
        label: label || undefined,
        limit: 25
      });
      setResults(found);
      setStatusMessage(`${found.length} result${found.length === 1 ? "" : "s"} found`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to search graph.");
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

  function handleIncludeArchivedChange(nextIncludeArchived: boolean) {
    setIncludeArchived(nextIncludeArchived);
    if (selectedNodeId) {
      void loadNodeContext(selectedNodeId, depth, nextIncludeArchived);
    }
  }

  return (
    <div className="workspace graph-workspace memory-graph-workspace">
      <GraphContextBar
        query={query}
        label={label}
        depth={depth}
        includeArchived={includeArchived}
        isLoading={isLoading}
        statusMessage={statusMessage}
        errorMessage={errorMessage}
        onQueryChange={setQuery}
        onLabelChange={setLabel}
        onDepthChange={handleDepthChange}
        onIncludeArchivedChange={handleIncludeArchivedChange}
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

        {selectedNodeId ? (
          <GraphInspectorPanel detail={detail} selectedNodeId={selectedNodeId} />
        ) : (
          <GraphSearchWindow
            results={results}
            selectedNodeId={selectedNodeId}
            onSelectNode={(id) => void loadNodeContext(id)}
          />
        )}
      </div>
    </div>
  );
}
