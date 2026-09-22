# AI engineering foundations

This folder will contain the concise, canonical principles that govern every
AI-related implementation. Existing broad principles remain in the parent
README as retained baseline material until they are decomposed and explicitly
superseded.

## Initial decisions

- DTO-first and annotation-first design is mandatory at every application
  boundary.
- Provider tool-call IDs are preserved and normalized by adapters.
- Tool invocation, provider protocols, and final user responses are distinct
  layers.
- Prompts influence behavior; typed contracts and backend code enforce it.
