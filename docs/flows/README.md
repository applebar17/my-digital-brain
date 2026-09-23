# Flows

End-to-end product and backend workflows. A flow describes the expected
sequence and handoffs; DTO and API shape belongs to the relevant contract
documentation.

## Contents

- [Ingestion](ingestion.md)
- [Structured ingestion objects](structured-ingestion-objects.md)
- [Entity resolution](entity-resolution.md)
- [Interrogation](interrogation.md)
- [Memory-management agent](memory-management-agent.md)

## Temporary documentation migration ledger

| File | Transaction action |
| --- | --- |
| `ingestion.md` | Keep the user-visible ingestion behavior; remove or link out superseded runtime mechanics. |
| `entity-resolution.md` | Keep the functional identity-resolution behavior; align its references with the clean-slate context contracts. |
| `interrogation.md` | Keep the functional querying behavior; align provider/runtime references. |
| `memory-management-agent.md` | Keep only accepted product behavior; move agent-framework detail to `ai-engineering/`. |
| `structured-ingestion-objects.md` | Review in detail. Migrate still-valid semantic/domain concepts to `network/` and typed AI contracts to `ai-engineering/`, then delete this duplicate object catalogue. |

This table is removed after the listed transactions are complete.
