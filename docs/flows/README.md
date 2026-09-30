# Flows

End-to-end product and backend workflows. A flow describes the expected
sequence and handoffs; DTO and API shape belongs to the relevant contract
documentation.

## Contents

- [Ingestion](ingestion.md)
- [Structured ingestion objects](structured-ingestion-objects.md)
- [Entity resolution](entity-resolution.md)
- [Interrogation](interrogation.md)
- [Flow documentation migration](flow-documentation-migration.md): temporary
  keep/move/delete plan for this folder; delete it when the migration completes.

## Temporary documentation migration ledger

| File | Transaction action |
| --- | --- |
| `ingestion.md` | Keep the user-visible ingestion behavior; remove or link out superseded runtime mechanics. |
| `entity-resolution.md` | Keep the functional identity-resolution behavior; align its references with the clean-slate context contracts. |
| `interrogation.md` | Keep the functional querying behavior; align provider/runtime references. |
| `memory-management-agent.md` | Migrated to `requirements/functional/memory-maintenance-and-corrections.md`; delete the old implementation-oriented document. |
| `structured-ingestion-objects.md` | Review in detail. Migrate still-valid semantic/domain concepts to `network/` and typed AI contracts to `ai-engineering/`, then delete this duplicate object catalogue. |

This table is removed after the listed transactions are complete.
