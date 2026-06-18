import { EmptyState } from "../../../components/EmptyState";
import { formatUnknown } from "../../../lib/graphLabels";
import type { SemanticMemoryHit, SemanticMemorySearchResult } from "../../../types/graph";

interface RetrievalDiagnosticsPanelProps {
  hit?: SemanticMemoryHit;
  retrievalResult?: SemanticMemorySearchResult;
}

export function RetrievalDiagnosticsPanel({
  hit,
  retrievalResult
}: RetrievalDiagnosticsPanelProps) {
  if (!hit && !retrievalResult) {
    return (
      <EmptyState
        title="No diagnostics"
        body="Run scoped semantic or hybrid retrieval to inspect scopes, scores, and hydration."
      />
    );
  }

  return (
    <section className="retrieval-diagnostics-panel">
      {hit ? (
        <div className="retrieval-diagnostic-grid">
          <Diagnostic label="Scope" value={hit.scope} />
          <Diagnostic label="Role" value={hit.hit_role} />
          <Diagnostic label="Matched" value={hit.matched_target_label ?? hit.matched_target_id} />
          <Diagnostic label="Display" value={hit.display_target_label ?? hit.display_target_id} />
          <Diagnostic label="Raw" value={hit.raw_score} />
          <Diagnostic label="Normalized" value={hit.normalized_score ?? hit.score} />
          <Diagnostic label="Weight" value={hit.scope_weight} />
          <Diagnostic label="Collection" value={hit.collection} />
        </div>
      ) : null}

      {hit?.hydration_path?.length ? (
        <div className="retrieval-path">
          {hit.hydration_path.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      ) : null}

      {retrievalResult?.trace?.length ? (
        <details className="memory-retrieval-trace" open={false}>
          <summary>Trace events</summary>
          <div>
            {retrievalResult.trace.map((event, index) => (
              <article key={`${event.stage}-${index}`} className={`memory-trace-event is-${event.status}`}>
                <b>{event.stage}</b>
                <span>{event.message}</span>
              </article>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function Diagnostic({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{formatUnknown(value)}</strong>
    </div>
  );
}
