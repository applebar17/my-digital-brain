import type { MemoryLogFilters as MemoryLogFilterValues } from "../../../api/graph";

interface MemoryLogFiltersProps {
  filters: MemoryLogFilterValues;
  isLoading: boolean;
  onChange: (filters: MemoryLogFilterValues) => void;
  onReset: () => void;
}

export function MemoryLogFilters({
  filters,
  isLoading,
  onChange,
  onReset
}: MemoryLogFiltersProps) {
  return (
    <form className="memory-log-filters" onSubmit={(event) => event.preventDefault()}>
      <label>
        <span>From</span>
        <input
          type="date"
          value={filters.from_time ?? ""}
          disabled={isLoading}
          onChange={(event) => onChange({ ...filters, from_time: event.target.value || undefined })}
        />
      </label>
      <label>
        <span>To</span>
        <input
          type="date"
          value={filters.to_time ?? ""}
          disabled={isLoading}
          onChange={(event) => onChange({ ...filters, to_time: event.target.value || undefined })}
        />
      </label>
      <label>
        <span>Kind</span>
        <input
          value={filters.log_kind ?? ""}
          disabled={isLoading}
          placeholder="update"
          onChange={(event) => onChange({ ...filters, log_kind: event.target.value || undefined })}
        />
      </label>
      <label>
        <span>Source</span>
        <input
          value={filters.source_kind ?? ""}
          disabled={isLoading}
          placeholder="chat"
          onChange={(event) => onChange({ ...filters, source_kind: event.target.value || undefined })}
        />
      </label>
      <label>
        <span>Involved</span>
        <input
          value={filters.involved_target_id ?? ""}
          disabled={isLoading}
          placeholder="target id"
          onChange={(event) => onChange({ ...filters, involved_target_id: event.target.value || undefined })}
        />
      </label>
      <label>
        <span>Limit</span>
        <input
          min={1}
          max={200}
          type="number"
          value={filters.limit ?? 50}
          disabled={isLoading}
          onChange={(event) => {
            const value = Number(event.target.value);
            onChange({ ...filters, limit: Number.isFinite(value) ? value : undefined });
          }}
        />
      </label>
      <label className="memory-log-filter-toggle">
        <input
          type="checkbox"
          checked={Boolean(filters.media_only)}
          disabled={isLoading}
          onChange={(event) => onChange({ ...filters, media_only: event.target.checked })}
        />
        <span>Media</span>
      </label>
      <label className="memory-log-filter-toggle">
        <input
          type="checkbox"
          checked={Boolean(filters.include_archived)}
          disabled={isLoading}
          onChange={(event) => onChange({ ...filters, include_archived: event.target.checked })}
        />
        <span>Archived</span>
      </label>
      <button type="button" disabled={isLoading} onClick={onReset}>
        Reset
      </button>
    </form>
  );
}
