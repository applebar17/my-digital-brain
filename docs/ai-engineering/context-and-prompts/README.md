# Context and prompts

This folder owns model-facing instructions and context construction policies.

## Contents

- [Context package contract](context-package-contract.md): typed context
  construction, rendering boundaries, model-visible selection rules, and nested
  state restriction.
- [Reference context and owner projection](reference-context-and-owner-projection.md):
  run-scoped model references, owner packet, private ID mapping, and rendering
  levels 0–2.
- [Prompting guidelines](prompting-guidelines.md).
- [Prompt lifecycle and versioning](prompt-lifecycle-and-versioning.md):
  file-backed versioned templates, typed runtime rendering, trace snapshots,
  and migration of code constants.

Concrete state documents own prompt behavior. Prompt lifecycle owns template
selection and versioning; this folder does not maintain a second state/prompt
inventory.

## Boundary

Prompts guide behavior. DTO field descriptions define expected data. Backend
code owns validation, execution ordering, IDs, authorization, and persistence.
No prompt may be relied on to repair a broken tool-call transcript.
