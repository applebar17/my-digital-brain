# Context and prompts

This folder owns model-facing instructions and context construction policies.

## Planned contents

- Context package contracts and rendering levels.
- [Prompting guidelines](prompting-guidelines.md).
- [Prompt lifecycle and versioning](prompt-lifecycle-and-versioning.md):
  file-backed versioned templates, typed runtime rendering, trace snapshots,
  and migration of code constants.
- [Prompt inventory](prompt-inventory.md).
- Prompt rendering tests and example fixtures.
- Guidance for reference aliases, summaries, and user-safe language.

## Boundary

Prompts guide behavior. DTO field descriptions define expected data. Backend
code owns validation, execution ordering, IDs, authorization, and persistence.
No prompt may be relied on to repair a broken tool-call transcript.
