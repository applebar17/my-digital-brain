interface IntegrityPanelProps {
  contradictions: number;
  staleItems: number;
  orphanedRefs: number;
}

export function IntegrityPanel({ contradictions, staleItems, orphanedRefs }: IntegrityPanelProps) {
  return (
    <div className="memory-integrity-panel">
      <div className="memory-integrity-score">
        <strong>{contradictions}</strong>
        <span>Unresolved contradictions</span>
      </div>
      <div className="memory-integrity-list">
        <div>
          <span>Stale items</span>
          <b>{staleItems}</b>
        </div>
        <div>
          <span>Orphaned refs</span>
          <b>{orphanedRefs}</b>
        </div>
      </div>
      <p>Maintenance workflows are placeholders until graph review services are wired.</p>
    </div>
  );
}
