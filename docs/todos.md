# Project TODOs

This file contains only unfinished product or engineering work. Completed
implementation waves are recorded briefly below for orientation, not as active
tasks.

Priority scale: `1` is highest urgency and `5` is lowest.

## Completed Baseline

The following foundations are implemented and should not be reopened as new
features:

- Canonical owner bootstrap, `OWNER` alias, owner integrity validation, and
  protected `Person.is_owner` writes.
- Candidate identity planning, deterministic lookup, bounded graph context,
  run-scoped uppercase references, clarification-aware resolution, and staged
  write-plan validation.
- Clarification Waves 0-7: handoff agent, channel-neutral packets, read-only
  context tools, grouped continuation, text-based web/Telegram/terminal flows,
  master-history promotion, child-frame retention, prompt policy, and frontend
  status/error handling.
- Unified `run_session()` with structured output, provider-independent tool
  loops, pending external interactions, grouped continuation, and repair.
- Reusable reasoning/planning states, whole-source graph context packs, state
  history projection, structured contradiction review, and frame-based final
  assistant ownership.

## Identity And Ingestion Hardening

Priority: 1

- Build a regression corpus from real UAT traces covering:
  - exact graph match;
  - multiple exact or partial matches;
  - fuzzy-only candidates;
  - no candidates;
  - user clarification followed by attach, create-new, or keep-ambiguous.
- Verify that every resolution batch receives its own candidates plus the
  relevant references outside the batch, without persisted graph IDs.
- Revalidate model references and graph state after a clarification and again
  immediately before write execution. Account for graph changes made while a
  session is paused.
- Add the qualitative duplicate-judge step before durable entity writes. Define
  attach, create-new, user-confirmed merge, metadata transfer, archival, and
  re-embedding behavior without making the backend choose the LLM's semantic
  decision.
- Resolve the alias policy. Aliases are lookup and context hints, but current
  serializers persist them for labels that allow the property. Decide which
  aliases are durable node data and enforce that decision consistently.
- Keep the current boundary: backend searches, validates, and writes; the LLM
  chooses the semantic identity action from supplied context.

## Application Identity, Export, MCP, And Integrations

Priority: 1

- Add authentication and account lifecycle management for web, Telegram-linked
  accounts, terminal/local use, and future API clients.
- Define user and graph authorization boundaries. Requests must resolve an
  authorized user and graph scope rather than trusting client-supplied owner or
  graph IDs.
- Add user-initiated database export/download with schema versioning, graph and
  source provenance, media references, sensitive-data handling, authorization,
  audit logging, idempotency, and streaming for large exports.
- Decide import/restore compatibility separately from export format design.
- Package a locally installable MCP integration for a user's connected or
  exported database. Use least-privilege tools and preserve the model-facing
  reference rules; raw graph queries and unrestricted credentials are excluded
  by default.
- Define MCP installation, local transport, credentials, revocation, updates,
  and version compatibility.
- Design a secure external integration API with registered integrations,
  scoped credentials, token rotation and revocation, per-user/per-graph
  authorization, capability-scoped read/write permissions, rate limits, audit
  events, replay protection, and structured errors.
- Add security, isolation, export, MCP, and external-client contract tests
  before exposing these surfaces generally.

## Clarification And Ingestion Evaluation

Priority: 1

- Evaluate multilingual and user-friendly wording for no-match, duplicate,
  missing-field, correction, confirmation, relationship-target, and
  multi-question scenarios.
- Verify terminal, web, and Telegram packet rendering and resume behavior from
  real channel traces, including retryable errors, delayed answers, and edits.
- Confirm that clarification answers are promoted to structured candidate fields
  and that the current resolution session continues without restarting ingestion.
- Keep prompt guidance non-deterministic: statuses remain model guidance and do
  not become backend semantic gates.
- Keep browser media capture, upload, storage, and transcription deferred.

## Owner Profile Retrieval And Approval

Priority: 2

The approved-only reader, owner scoping, review service, prompt projection, and
read-only profile-duplication state exist. Remaining work is integration and
operational verification:

- Expose explicit owner-profile purposes through the supported application/API
  boundary without adding profile traits to generic retrieval.
- Wire user confirmation and rejection through an authenticated owner-scoped
  workflow, including audit records.
- Verify profile vector inclusion/exclusion and refresh behavior against the real
  vector store, including hidden, temporary, inferred-unconfirmed, archived,
  and confirmation-required records.
- Test personality-duplication consumers as read-only users of the approved
  snapshot with no graph-write capability.

## Unified Session And Handoff Verification

Priority: 2

- Run opt-in provider checks for plain text, structured output, tool loops,
  structured repair, nested sessions, and pending clarification resume.
- Verify the configurable tool budget: complete assistant batches execute,
  toolbox removal happens on the next provider turn, and pending calls resume
  with one matching tool output each.
- Audit all agentic states and backend tools for compact upward handoffs. Keep
  state-local message deltas for replay, but do not expose nested provider traces
  as top-level model context.
- Verify all consumers use `run_session()` and that removed generation
  entrypoints do not return through compatibility wrappers.

## History And Context Projection

Priority: 2

- Complete the cross-channel audit of `AgenticHistoryService`, master history,
  child transcripts, and state-specific projections.
- Verify that role-preserved history contains the original conversation once,
  clarification exchanges in order, and no raw schemas, packet IDs, graph IDs,
  provider diagnostics, or internal reasoning.
- Add a future context-compaction service after a configurable provider-context
  threshold. Preserve recent messages and important promoted clarification
  exchanges while emitting no backend metadata.

## Prompt Inventory And Runtime Cleanup

Priority: 2

- Reconcile `docs/ai-engineering/prompt-inventory.md` with actual ownership.
  `ProfileMemoryExtractor` remains wired in the ingestion factory, so
  `profile_memory_extraction` must either be documented as active or migrated
  deliberately before removal.
- Remove stale documentation and inactive prompt mappings only after production
  references are verified. Do not add compatibility aliases or duplicate prompt
  owners.
- Complete the ingestion runtime audit: production flow is reasoning-first, but
  UAT helpers and historical documents still contain older planner terminology.

## Typed Node Identity Fields

Priority: 3

- Add optional `given_name` and `family_name` for `Person` without requiring a
  surname for mononyms or incomplete identities.
- Define type-specific identity fields for Event, Place, Organization, Object,
  and other named node types.
- Define normalization and lookup for full names, aliases, nicknames, compound
  surnames, and incomplete names.
- Extend candidate contracts, graph models, migrations, lookup, rendering,
  prompts, and tests together while preserving `display_name` as the universal
  human-readable field.

## Place Search And Geocoding

Priority: 3

- Add a backend-owned place-search tool accepting a candidate name and optional
  location hints.
- Return provider place ID, canonical name, address, city, country,
  coordinates, maps URL, and provenance. The LLM may select a supplied result
  but may not invent coordinates or URLs.
- Define provider configuration, rate limits, caching, no-match/multi-match
  behavior, approval, idempotency, and cross-graph isolation.

## MemoryLog And Node Update Flow

Priority: 3

Design is captured in
[MemoryLog vectorization and node update flow](dev-plans/11-node-log-vectorization-and-update-flow.md).

- Add first-class semantic `MemoryLog` records with multiple host and involved
  links while retaining one primary host.
- Add agentic node-update tooling for MemoryLogs, safe patches, and vectors with
  deterministic backend guardrails.
- Add micro-log vectorization using the shared embedding configuration and
  hydrate retrieval back to canonical nodes.
- Later, refresh node summaries and summary embeddings when important logs or
  derived context change.

## Observability And Retrieval Rendering

Priority: 3

- Add richer sanitized trace metadata for state, model task/route, conversation,
  owner scope, ingestion session, tool names, handoff targets, status, and error
  codes. Never include raw personal memory text, graph payloads, or credentials.
- Decide whether local JSONL traces are sufficient or a separate state-transition
  artifact is needed.
- Compare retrieval thresholding strategies for graph workspace rendering while
  keeping agentic retrieval broader than UI rendering.

## Media And UX Follow-Ups

Priority: 4

- Audit `MediaAsset`, source records, `HAS_MEDIA` links, derived artifacts, and
  media ownership/idempotency behavior. Core media models and links exist, but
  the end-to-end policy audit is unfinished.
- Define media link role, evidence span, confidence, provenance, lifecycle,
  visibility, ordering, and duplicate handling.
- Add per-chat archive actions in the recent-chat sidebar using session status,
  not hard deletion.
