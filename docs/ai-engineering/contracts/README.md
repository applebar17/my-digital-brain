# AI contracts

This folder defines the application contracts at every AI boundary. Contracts
are the source of truth for application behavior; prompts and provider payloads
are generated from or checked against them.

## Contents

- [DTO-first contract baseline](dto-first-contracts.md): required shape of tool
  definitions, calls, outputs, errors, structured model output, and validation.
- [Generalized AI principles](generalized-ai-principles.md): retained broad
  cross-use-case principles to classify into the canonical documents over time.

## Ownership

- Provider adapters normalize provider-native payloads into the runtime DTOs.
- Tool registrations own input/output DTO types and their implementation.
- The runtime owns call identity, execution ordering, and transcript validity.
- Domain services own domain validation and persistent state changes.

No provider-native object, raw JSON dictionary, or database record may become a
cross-layer contract by convention.
