import { EmptyState } from "../../../components/EmptyState";
import { nodeId, nodeTitle } from "../../../lib/graphLabels";
import type { GraphSearchMode, NodeSearchResult, SemanticMemorySearchResult } from "../../../types/graph";

interface GraphSearchWindowProps {
  searchMode: GraphSearchMode;
  results: NodeSearchResult[];
  retrievalResult?: SemanticMemorySearchResult;
  selectedNodeId?: string;
  onSelectNode: (nodeId: string) => void;
}

export function GraphSearchWindow({
  searchMode,
  results,
  retrievalResult,
  selectedNodeId,
  onSelectNode
}: GraphSearchWindowProps) {
  const hitCount = retrievalResult?.hits.length ?? 0;
  const count = searchMode === "property" ? results.length : hitCount;

  return (
    <aside className="memory-window memory-search-window">
      <header className="memory-window-header">
        <div>
          <p className="eyebrow">Seed Navigation</p>
          <h3>{searchMode === "property" ? "Search Results" : "Retrieval Hits"}</h3>
        </div>
        <span className="memory-window-count">{count}</span>
      </header>
      {searchMode === "property" ? (
        <PropertyResults
          results={results}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
        />
      ) : (
        <RetrievalResults
          retrievalResult={retrievalResult}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
        />
      )}
    </aside>
  );
}

function PropertyResults({
  results,
  selectedNodeId,
  onSelectNode
}: Pick<GraphSearchWindowProps, "results" | "selectedNodeId" | "onSelectNode">) {
  return (
    <div className="memory-result-list">
      {results.length === 0 ? (
        <EmptyState title="No seed selected" body="Search for a node to render its graph neighborhood." />
      ) : (
        results.map((node) => {
          const id = nodeId(node);
          return (
            <button
              className={`memory-result ${selectedNodeId === id ? "is-active" : ""}`}
              key={id || nodeTitle(node)}
              type="button"
              onClick={() => onSelectNode(id)}
            >
              <span>{nodeTitle(node)}</span>
              <small>{node.label}</small>
            </button>
          );
        })
      )}
    </div>
  );
}

function RetrievalResults({
  retrievalResult,
  selectedNodeId,
  onSelectNode
}: Pick<GraphSearchWindowProps, "retrievalResult" | "selectedNodeId" | "onSelectNode">) {
  const hits = retrievalResult?.hits ?? [];
  return (
    <div className="memory-result-list">
      {hits.length === 0 ? (
        <EmptyState title="No retrieval hits" body="Run semantic or hybrid search to hydrate graph memories." />
      ) : (
        hits.map((hit) => {
          const targetId = hit.display_target_id || hit.canonical_target_id || hit.primary_target_id;
          const title = hit.title || hit.target?.title || hit.canonical_target?.title || "Untitled result";
          return (
            <button
              className={`memory-result memory-retrieval-hit ${selectedNodeId === targetId ? "is-active" : ""}`}
              key={`${hit.source}-${targetId}-${hit.rank}`}
              type="button"
              onClick={() => onSelectNode(targetId)}
            >
              <span>{title}</span>
              <small>
                #{hit.rank} {hit.display_target_label || hit.primary_target_label} -{" "}
                {hit.hit_role || hit.source} - {hit.score.toFixed(2)}
              </small>
              {(hit.description || hit.document_preview) && (
                <em>{hit.description || hit.document_preview}</em>
              )}
            </button>
          );
        })
      )}
      {retrievalResult && retrievalResult.trace.length > 0 && (
        <details className="memory-retrieval-trace">
          <summary>Retrieval trace</summary>
          <div>
            {retrievalResult.trace.map((event, index) => (
              <article key={`${event.stage}-${index}`} className={`memory-trace-event is-${event.status}`}>
                <b>{event.stage}</b>
                <span>{event.message}</span>
              </article>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
