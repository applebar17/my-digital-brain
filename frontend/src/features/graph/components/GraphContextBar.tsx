import type { FormEvent } from "react";
import { graphNodeLabels } from "../utils/graphDisplay";

interface GraphContextBarProps {
  query: string;
  label: string;
  depth: number;
  includeArchived: boolean;
  showDatabaseSample: boolean;
  databaseSampleLimit: number;
  isLoading: boolean;
  statusMessage?: string;
  errorMessage?: string;
  onQueryChange: (query: string) => void;
  onLabelChange: (label: string) => void;
  onDepthChange: (depth: number) => void;
  onIncludeArchivedChange: (includeArchived: boolean) => void;
  onShowDatabaseSampleChange: (showDatabaseSample: boolean) => void;
  onDatabaseSampleLimitChange: (limit: number) => void;
  onSearch: (event?: FormEvent<HTMLFormElement>) => void;
}

export function GraphContextBar({
  query,
  label,
  depth,
  includeArchived,
  showDatabaseSample,
  databaseSampleLimit,
  isLoading,
  statusMessage,
  errorMessage,
  onQueryChange,
  onLabelChange,
  onDepthChange,
  onIncludeArchivedChange,
  onShowDatabaseSampleChange,
  onDatabaseSampleLimitChange,
  onSearch
}: GraphContextBarProps) {
  return (
    <form className="memory-context-bar" onSubmit={onSearch}>
      <div className="memory-context-title">
        <p className="eyebrow">Memory Graph</p>
        <h2>Graph Workspace</h2>
      </div>

      <label className="memory-search-field">
        <span>Search</span>
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search current context..."
        />
      </label>

      <label className="memory-control-field">
        <span>Type</span>
        <select value={label} onChange={(event) => onLabelChange(event.target.value)}>
          {graphNodeLabels.map((item) => (
            <option key={item || "all"} value={item}>
              {item || "All"}
            </option>
          ))}
        </select>
      </label>

      <label className="memory-control-field">
        <span>Depth</span>
        <input
          value={depth}
          onChange={(event) => onDepthChange(Number(event.target.value))}
          type="number"
          min="1"
          max="3"
        />
      </label>

      <label className="memory-check-field">
        <input
          checked={includeArchived}
          onChange={(event) => onIncludeArchivedChange(event.target.checked)}
          type="checkbox"
        />
        Archived
      </label>

      <label className="memory-check-field">
        <input
          checked={showDatabaseSample}
          onChange={(event) => onShowDatabaseSampleChange(event.target.checked)}
          type="checkbox"
        />
        DB sample
      </label>

      <label className="memory-control-field memory-sample-limit-field">
        <span>Max nodes</span>
        <input
          value={databaseSampleLimit}
          onChange={(event) => onDatabaseSampleLimitChange(Number(event.target.value))}
          type="number"
          min="1"
          max="100"
          disabled={!showDatabaseSample}
        />
      </label>

      <div className="memory-trust-legend" aria-label="Trust legend">
        <span><i className="legend-dot legend-verified" />Verified</span>
        <span><i className="legend-dot legend-inferred" />Inferred</span>
        <span><i className="legend-dot legend-disputed" />Disputed</span>
      </div>

      <button className="memory-primary-action" type="submit" disabled={isLoading}>
        {isLoading ? "Loading" : "Search"}
      </button>

      {(statusMessage || errorMessage) && (
        <p className={`memory-status ${errorMessage ? "is-error" : ""}`}>
          {errorMessage ?? statusMessage}
        </p>
      )}
    </form>
  );
}
