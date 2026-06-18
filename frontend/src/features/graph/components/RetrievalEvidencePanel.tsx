import { EmptyState } from "../../../components/EmptyState";
import { formatUnknown } from "../../../lib/graphLabels";
import type { GraphContextPackage, SemanticMemoryHit } from "../../../types/graph";

interface RetrievalEvidencePanelProps {
  hit?: SemanticMemoryHit;
  contextPackages: GraphContextPackage[];
}

export function RetrievalEvidencePanel({ hit, contextPackages }: RetrievalEvidencePanelProps) {
  const records = [
    ...(hit?.matched_records ?? []),
    ...contextPackages.flatMap((contextPackage) => contextPackage.matched_records ?? [])
  ];
  const uniqueRecords = dedupeRecords(records);

  if (uniqueRecords.length === 0) {
    return (
      <EmptyState
        title="No matched evidence"
        body="Run semantic or hybrid retrieval to see exact matched records for this node."
      />
    );
  }

  return (
    <section className="retrieval-evidence-panel">
      {uniqueRecords.slice(0, 8).map((record, index) => (
        <article key={`${formatUnknown(record.label)}-${index}`}>
          <header>
            <strong>{formatUnknown(record.title ?? record.label)}</strong>
            <span>{formatUnknown(record.label ?? record.hit_role ?? record.scope)}</span>
          </header>
          {record.description ? <p>{formatUnknown(record.description)}</p> : null}
          {record.document_preview ? <p>{formatUnknown(record.document_preview)}</p> : null}
          <small>
            {formatUnknown(record.scope)}
            {record.score !== undefined ? ` - ${formatUnknown(record.score)}` : ""}
          </small>
        </article>
      ))}
    </section>
  );
}

function dedupeRecords(records: Record<string, unknown>[]): Record<string, unknown>[] {
  const seen = new Set<string>();
  const deduped: Record<string, unknown>[] = [];
  records.forEach((record) => {
    const key = JSON.stringify([record.label, record.title, record.description, record.document_preview]);
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    deduped.push(record);
  });
  return deduped;
}
