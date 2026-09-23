# AI runtime migration

This folder records the controlled transition from the current AI runtime to
the documented target. It prevents reference code and experimental behavior
from silently becoming production architecture.

## Contents

- [Reference client assessment](reference-ai-clients-assessment.md): what the
  imported `ai_clients` package demonstrates, what must not be copied, and its
  current repository status.
- [Client-runtime rebuild plan](client-runtime-rebuild-plan.md): inventory,
  endpoint decision, migration waves, and exit criteria.

## Rules

- No production import may be switched to a reference package without a
  reviewed migration plan, DTO conformance tests, and removal of superseded code.
- There is one canonical runtime after migration; adapters and compatibility
  shims are temporary and have explicit retirement tasks.
- A migration wave changes one boundary at a time and commits independently.

## Temporary documentation migration ledger

These two files exist only to guide the implementation transition. Keep them
current while the clean-slate runtime is being migrated; once that migration is
complete, delete this folder's transition documents rather than retaining them
as future implementation guidance.
