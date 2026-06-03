import { EmptyState } from "../../../components/EmptyState";
import { compactId, nodeId, nodeTitle } from "../../../lib/graphLabels";
import type { NodeSearchResult } from "../../../types/graph";

interface GraphSearchWindowProps {
  results: NodeSearchResult[];
  selectedNodeId?: string;
  onSelectNode: (nodeId: string) => void;
}

export function GraphSearchWindow({ results, selectedNodeId, onSelectNode }: GraphSearchWindowProps) {
  return (
    <aside className="memory-window memory-search-window">
      <header className="memory-window-header">
        <div>
          <p className="eyebrow">Seed Navigation</p>
          <h3>Search Results</h3>
        </div>
        <span className="memory-window-count">{results.length}</span>
      </header>
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
                <small>
                  {node.label} {id ? compactId(id) : ""}
                </small>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
