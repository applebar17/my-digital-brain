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
