# AI contracts

This folder defines the application contracts at every AI boundary. Contracts
are the source of truth for application behavior; prompts and provider payloads
are generated from or checked against them.

## Contents

- [DTO-first contract baseline](dto-first-contracts.md): required shape of tool
  definitions, calls, outputs, errors, structured model output, and validation.
- [Tool definition and toolbox contracts](tool-definition-and-toolbox.md):
  typed tool registration, semantic field schemas, OpenAI function-declaration
  adapters, state-specific toolbox composition, and retirement of string
  dispatch.
- `generalized-ai-principles.md`: temporary source for reviewed concept
  migration; it is not an active contract and is deleted when complete.

## Ownership

- Provider adapters normalize provider-native payloads into the runtime DTOs.
- Tool registrations own input/output DTO types and their implementation.
- The runtime owns call identity, execution ordering, and transcript validity.
- Domain services own domain validation and persistent state changes.

No provider-native object, raw JSON dictionary, or database record may become a
cross-layer contract by convention.

## Temporary documentation migration ledger

Keep the focused DTO and toolbox contracts. Review
`generalized-ai-principles.md` rule by rule, move a still-valid rule to its
specific owner in `contracts/`, `runtime/`, `context-and-prompts/`, or another
canonical folder, then delete `generalized-ai-principles.md`. It must not remain
as a competing broad contract.
