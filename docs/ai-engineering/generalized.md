# Use-Case-Agnostic AI Engineering Principles

## Purpose

These principles guide how AI features should be designed and implemented in
systems that combine model reasoning, structured outputs, tools, retrieval, and
guarded persistence.

The goal is not to make every flow deterministic. The goal is to use model
reasoning where it is valuable, while keeping enough structure around it to make
the system reliable, debuggable, and safe.

## Core Principles

### 1. Structure Unstructured Input Explicitly

Information is extracted from unstructured text, transcripts, media-derived
text, documents, and interaction history through explicit structurization
processes.

When asking a model to extract information, the request should include the
expected structured output contract, preferably as a Pydantic object or
equivalent schema. The model should produce structured proposals, not direct
persistent-state mutations.

LLM-facing extraction contracts must be semantic draft contracts. The model
extracts meaning, local candidate refs, provided aliases, evidence text/spans,
and property suggestions. Backend code deterministically enriches those drafts
into records with source IDs, generated IDs, evidence refs, status fields,
timestamps, metadata, and persistence-ready provenance.

Rules:

- Use `*Draft` schemas for provider structured outputs.
- Use enriched backend records for validation, resolution, write plans, storage,
  and audit.
- Do not ask the model to echo `source_id`, generated IDs, raw UUIDs,
  `EvidenceRef`, `source_refs`, or backend metadata.
- Let the model use only scoped local refs such as `CANDIDATE_OBJECT_001` and
  provided aliases such as `RECORD_000001`.
- Represent arbitrary metadata as typed property suggestions in model-facing
  schemas; backend code decides whether they become typed fields or metadata.

Input-to-state flows use two freedom tiers:

- High-freedom semantic planning: the planner organizes the source narrative
  into ordered semantic actions, goals, evidence spans, dependencies,
  ambiguity/context gaps, and clarification needs. It must not choose storage
  categories, association types, write-plan operations, persistence fields, or
  backend-owned IDs.
- Low-freedom backend-facing extraction: focused extractors return enum-bound
  candidate drafts using only allowed vocabulary and refs/aliases supplied in
  the current step. Backend code compiles semantic actions into these
  constrained calls, injects deterministic IDs/provenance, validates refs and
  allowed values, and owns persistent writes.

State-changing reasoning flows should use a stricter baseline:

- Whole-source retrieval builds compact stored-context before reasoning.
- A structured reasoning checkpoint interprets domain objects, aliases,
  associations, user/owner involvement, salience, ambiguity, and storage
  cautions before planning.
- Object planning and association planning are separate model steps.
- Object candidates are prepared and validated before association planning.
- Association planning receives a resolved object map and must not invent
  unresolved referenced objects.
- Durable writes happen only after backend validation and write-plan assembly.

The model may use local refs only when the process goal requires orchestration
between objects. A ref-consuming extraction step may use only refs created by
earlier steps or aliases explicitly provided by the backend.

The backend must guarantee executable ordering. In a reasoning-first intake
baseline, association planning starts only after object validation has produced
a resolved object map. If an association step discovers that a required object
is missing, it must emit `missing_object_required` and loop back through
supplemental object handling before any association candidate is accepted.

Reasoning checkpoints are allowed before important downstream steps when the
process needs richer context interpretation. A reasoning checkpoint receives
purpose-specific guidelines, usable history, compact stored-context, and caller
input, then returns structured context augmentations. It may recommend
clarifications, object-versus-metadata handling, owner/user interpretation,
context treatment, context gaps, and guardrails. It does not own persistent
mutation, write-plan construction, validation, or schema compilation.

Reasoning outputs should be structured decision notes and interpretations, not
hidden chain-of-thought. Their purpose is to reduce later ambiguity, such as
clarifying that a short name is an alias for an existing person instead of a
separate person.

Reasoning and planning should both be treated as reusable LLM-backed
information transforms. The baseline package shape is:

```text
general system prompt template
  + dedicated purpose/guidelines
  + dedicated context information
  + usable history when relevant
  + optional prior compact tool outputs
  + selected model route
  + dedicated structured output model
  -> structured artifact
```

A reasoning checkpoint should follow this shape through purpose guidelines,
caller input context, optional interaction and stored-context, prior tool
outputs, model routing, and caller-selected output schemas. Planning should
mirror the same pattern: a generalized planning primitive should convert a goal,
context, reasoning artifact, and constraints into ordered process actions. It
should not extract candidates, validate candidates, resolve duplicates, build
write plans, or mutate storage.

If a state needs a structured artifact as its final useful result, that artifact
should be the state's validated structured output, not a fake "submit" tool used
only to smuggle the schema back to the backend. Tools may still be used inside
the state for support actions such as context expansion or inconsistency review.
After the structured output is returned, backend code deterministically routes
the next process step from that schema.

Examples:

- Candidate domain objects.
- Candidate associations.
- Candidate claims.
- Candidate metadata patches.
- Candidate clarification questions.
- Candidate tool calls.

### 2. Schemas And Tool Descriptions Are Prompt Surface

Pydantic field descriptions, JSON schema descriptions, tool names, tool
descriptions, enum values, and parameter descriptions are part of the prompt.

They must be:

- Clear.
- Unambiguous.
- Task-specific.
- Short enough to avoid noise.
- Explicit about constraints and expected behavior.

Bad schema descriptions can confuse the model as much as bad prompt text.

### 3. Prefer Modular Model Calls Over Heavy Requests

Large overloaded prompts increase hallucination risk and make failures harder to
debug.

Prefer modular steps when useful:

- Whole-source context retrieval.
- Compact context packaging.
- Structured reasoning checkpoints.
- Object planning.
- Object extraction.
- Object resolution support.
- Association planning.
- Association extraction.
- Inconsistency detection.
- Answer generation.
- Tool selection.

Inconsistency handling should prefer a specialized judge call when there is
meaningful doubt. A state-changing agent should not rely on brittle
deterministic inconsistency rules; it should inspect retrieved context and
invoke the judge when it can explain the suspected conflict.

Modularity should reduce cognitive load for the model, but it should not add
unnecessary latency or cost for trivial tasks.

For information intake, complexity is decided after lightweight context
retrieval. Raw text alone is not enough to know whether an input is simple or
ambiguous. The expected sequence is:

1. Whole-source retrieval for relevant stored-context.
2. Compact context package construction.
3. Structured reasoning checkpoint.
4. Object-only planning.
5. Object candidate preparation.
6. Deterministic object validation and duplicate handling.
7. Association-only planning from the resolved object map.
8. Association candidate preparation.
9. Deterministic association validation.
10. Backend write-plan assembly and execution.

Generated natural-language query fan-out may be explored later. It is not
required for an initial reasoning-first intake baseline.

### 4. Use AI Dynamically Where It Adds Value

LLM-based systems should not be designed like purely deterministic software. A
good agent can use context, tools, and reasoning to handle cases that would
otherwise require many brittle branches.

For each problem, decide whether it is better solved by:

- Deterministic code.
- A constrained model call.
- An agent with tools.
- A hybrid approach.

The tradeoff is cost, latency, reliability, and implementation complexity. If a
deterministic solution is simple and reliable, use it. If the problem is
contextual, ambiguous, or language-heavy, use the model.

### 5. Context Building Is Fundamental

Every model step needs the right context for the job. Context should be
intentionally built, not dumped.

Context may include:

- Current user message.
- Relevant interaction history.
- Interrupted frame or clarification context.
- Retrieved domain objects.
- Source evidence.
- User or tenant preferences.
- Privacy and trust constraints.
- Tool results.
- Previous extraction candidates.
- Nearby stored-context for proposed writes.
- Current state plus relevant history when checking for inconsistency risk.

The context builder should ask: what information does this model call need to do
this job well, and what information would distract or bias it?

For state-changing calls, context should include enough nearby stored state for
the agent to notice possible inconsistencies: similar objects, current facts,
historical states, related sources, association contexts, time context, and
place context. This context enables agentic suspicion before an inconsistency
judge is invoked.

For a reasoning-first intake baseline, the first context strategy is
whole-source retrieval. The resulting context must be compacted before it is
injected into reasoning, so later model steps receive useful aliases,
associations, duplicate hints, and summaries instead of noisy storage payloads.

### 6. Tooling Enables Dynamic Processes

Actions, intent handling, and process management can be dynamic when the
orchestration layer has well-defined tools and proper context.

The model can infer which tool or pipeline is appropriate, but tools must have
clear contracts.

The LLM chooses actions and proposes parameters. Backend services validate
parameters and execute state changes. Tools are command surfaces, not authority
surfaces.

The default conversation-entry tool surface should stay small:

- `start_information_intake`
- `query_stored_context`
- `update_persistent_state`

Default answering is a non-tool path. Clarification handling, validation, write
execution, and lifecycle controls are not broad conversation-entry tools.
Clarification is handled as a continuation of the tool call that requested it:
the runtime persists an interrupted agentic frame with the assistant tool call
still open, the client returns structured answers, and the backend appends one
matching `tool` message before the same frame continues.

Good tools should:

- Have narrow responsibilities.
- Use clear input schemas.
- Return structured outputs.
- Preserve the provider message protocol: assistant tool calls are followed by
  matching `tool` messages keyed by `tool_call_id`.
- Be auditable when they change state.
- Fail explicitly.
- Avoid hidden side effects.

### 7. Define Agent Behavior Before Plugging Tools

In agentic development, define the behavioral protocol of the agent before
adding many tools.

The protocol should clarify:

- What the agent is responsible for.
- What it must never do.
- When it should ask the user.
- When it should call tools.
- Which tool calls require confirmation.
- How it handles uncertainty.
- How it recovers from invalid tool output.

Tools should then be added to support that behavior, not to let the agent
improvise without boundaries.

For inconsistency handling, the behavioral protocol is:

- State-changing agents may raise an inconsistency doubt when retrieved context
  conflicts with a proposed write.
- The doubt must include a short explanation grounded in provided context.
- An inconsistency judge tool reviews the doubt and may inspect more context
  through read-only tools.
- The judge returns a structured decision and recommended action.
- The judge does not mutate persistent state directly.

For persistent-state update flows, the model may choose a sequence of tools, but
each mutation must be a deterministic backend tool call. A v1 update state may
auto-execute structurally valid tool calls without a user confirmation gate;
invalid calls should return structured recoverable or blocking errors that guide
the model's next call. Physical deletion, merge behavior, archive-as-delete, and
destructive lifecycle transitions should remain outside the first update
toolbox unless an explicit policy is added.

### 8. Guardrails Protect Against Bad Loops

Agentic flows need deterministic guardrails to prevent unstable behavior.

Guardrails may include:

- Max tool-call iterations.
- Allowed tool sets per task.
- Required structured output validation.
- Confirmation before risky writes.
- Privacy checks before provider calls.
- Expiration for interrupted agentic frames.
- Retry limits.
- Fallback behavior.
- Read-only tool scopes for judge investigation.
- Mandatory structured outputs for judge decisions.

The agent can be dynamic inside the guardrails. The guardrails prevent runaway
loops, accidental writes, and confusing user experiences.

### 9. Manage Context Size Deliberately

Token budget is a product and engineering constraint.

The system should:

- Keep full usable conversation history available to top-level conversational
  states, including user messages, assistant messages, tool calls, and tool
  outputs.
- Summarize or compact older history when the message sequence becomes too long.
- Retrieve only relevant stored evidence.
- Avoid stuffing entire histories into prompts.
- Preserve durable facts in persistent storage instead of relying on chat
  history.
- Track which summaries are model-generated and when they were generated.

Summaries should preserve decisions, unresolved questions, object references,
and important user preferences.

### 10. Propagate History Down, Compact Tool Traces Up

Agentic history should preserve continuity without polluting later states with
noisy internal tool details.

Every state or tool invocation has a clear start and end. When it completes, it
returns exactly one tool output to its invoker, and the invoker appends that tool
output to the conversation/process history before the next invocation. That is
the normal context handoff across states.

Within one LLM state, tool calling follows the provider message protocol:

```text
assistant message with tool_calls
-> backend executes mapped tool function
-> tool message with the same tool_call_id
-> next model call
-> assistant message or another tool call
```

The backend maps tool names to partially initialized functions or methods,
validates and parses the tool arguments, executes the function, and serializes
the result as the `tool` message content. This loop may repeat autonomously
inside the state until the model returns a final assistant message or requests a
handoff. The runtime should preserve the state-local assistant/tool message
delta for tracing, replay, and later context construction.

Deterministic backend tools should return a structured activity summary:
status, important operations performed, validation errors, created or updated
refs, and the recommended next action. LLM-backed subprocesses should return the
final assistant/process result after their own internal iteration, not every
nested prompt, tool call, or trace event.

When an agentic state calls a tool or subprocess, the callee receives the parent
history plus the tool-call context it needs. As the execution moves deeper,
internal steps may append tool calls, tool outputs, diagnostics, and
intermediate results to the local trace.

When control returns to the caller, the caller's future model-facing history
should receive one compact tool output summary, not the full internal trace.

Rules:

- Moving deeper: pass the relevant parent history and append local tool status
  as needed.
- Moving upward: compact internal activity into a concise tool output result.
- For internal handoffs, include technical context only when the receiving state
  needs it for guidance or guardrails.
- For user-facing handoffs, hide technical fields and keep the assistant message
  simple, human-friendly, and non-diagnostic unless the user explicitly asks.
- Persist full internal traces for audit, debugging, and replay when useful.
- Local review reports may render prompts, inputs, outputs, candidates, and
  supplemental handling for human review; they are diagnostic artifacts, not
  model-facing history or production API contracts.
- Do not expose noisy nested tool chatter to future top-level prompts unless a
  state explicitly needs it.
- Tool output summaries must preserve the achieved result, unresolved
  questions, important errors, created/updated refs, and recommended next
  action.

This gives the model enough state to reason while avoiding history bloat and
hallucination pressure from irrelevant implementation details.

### 11. Pass Minimum Sufficient Context Per State

Every LLM-related state or procedure should receive the minimum collectable
context required to achieve its purpose.

This does not mean "little context." It means complete context for the task and
aggressive filtering of noise.

Each state configuration should define:

- Required context.
- Optional context.
- Forbidden or noisy context.
- History policy.
- Tool-trace policy.
- Prompt guidelines.
- Tool-call or structured-output contract.

For example, an intake reasoning checkpoint needs the user source text, usable
conversation history when relevant, the compact context package, current
time/timezone, and clarification answer context when resuming. It should not
receive raw database records, unrelated metadata blobs, or internal transport
details.

### 12. Persist Interrupted Frames, Not Pending Review States

Clarification is a provider-message continuation, not a separate pending review
workflow.

When an allowed state calls a clarification tool, the backend should:

- persist an agentic frame containing the state id, messages, compact context,
  trace, parent frame/tool-call refs, active clarification packet, and expiry;
- keep the assistant message with `tool_calls` in the stored frame and leave the
  matching tool output absent until the user answers;
- return a UI clarification packet containing `frame_id`, `tool_call_id`,
  `tool_name`, questions, options, and a human-readable history delta;
- validate submitted answers deterministically against the packet;
- append exactly one `tool` message with the original `tool_call_id`;
- continue the same state-local message history.

This keeps provider transcripts valid while avoiding a deterministic pending
review state. The UI may persist the clarification history delta as normal
conversation messages for future context, but the model continuation is governed
by the open tool call in the stored frame.

Nested agentic work follows the same rule. A parent state calls a tool; the
backend starts a child frame for the invoked state; the child may run its own
LLM/tool loop and request clarification; when the child completes, the parent
receives one compact tool output summarizing the child result, not the child's
full internal trace.

Structured clarification is a user-interaction contract, not a persistent-state
mutation. Model-facing history should receive the validated answer summary
through the tool output, not raw widget state or backend-only snapshots.

### 13. Keep Channel Metadata Backend-Owned By Default

Channel and session metadata should be modeled, stored, and available to backend
runtime code, but it should not be passed directly to the LLM by default.

The agent should receive only a minimal projection when the metadata changes its
behavior.

Potentially useful projections:

- Current time and timezone.
- Modality: text, voice transcript, image-derived text, or other source type.
- Transcript uncertainty when voice or media was involved.
- Rendering constraints such as short mobile-chat response versus richer web
  chat response.
- Source or attachment references when relevant.

Usually noisy or forbidden:

- Raw chat IDs.
- Webhook payloads.
- HTTP headers.
- Internal session identifiers.
- Transport-specific debug fields.

The backend can keep a `ChannelSessionMetadata` object for routing, auditing,
storage, and UI behavior. The context builder decides whether any projected
field belongs in a model prompt.

### 14. Route Tasks To Appropriate Models

Model choice should depend on task difficulty.

Use cheaper, faster models for:

- Simple classification.
- Format conversion.
- Basic extraction.
- Short summarization.
- Tool argument drafting with low risk.

Use stronger models for:

- Ambiguous object resolution.
- Complex extraction.
- Inconsistency reasoning.
- Multi-step planning.
- Sensitive or high-impact state updates.
- Final answers requiring careful synthesis.

The orchestration layer should eventually support model routing by task type,
expected difficulty, privacy level, latency budget, and cost budget.

### 15. Prompt Guardrails Should Be Restrictive But Natural

Prompts should restrict hallucination and unsafe behavior without making the
model rigid or unnatural.

Good guardrails:

- Tell the model what it can and cannot infer.
- Require uncertainty to be represented explicitly.
- Require evidence references when available.
- Forbid direct persistent-state mutation outside tools.
- Encourage clarification when needed.
- Allow graceful "unknown" answers.

Overly rigid prompts can make the agent brittle. Under-specified prompts invite
hallucination.

### 16. Simplify IDs In Model Context

Long opaque database IDs are bad prompt material. They increase token usage, are
hard for humans to inspect, and are easy for models to copy incorrectly.

When passing stored context to a model, the context builder should map internal
persistent IDs to short temporary aliases.

Example:

```text
Internal UUID 8f1f7c3a-... becomes RECORD_000001.
Internal UUID 17dc7a91-... becomes CLAIM_000001.
Internal UUID 72ad38f4-... becomes SOURCE_000001.
```

The model should use the aliases in structured outputs and tool arguments. The
backend must resolve aliases back to internal IDs before validation and
execution.

Rules:

- Aliases are scoped to a single model context or process step.
- Aliases are not canonical IDs.
- Alias maps should be explicit in the context.
- Failed alias resolution should fail validation.
- The model should never invent aliases that were not provided.

### 17. Build Low-Noise Context Packages

LLM context should be prepared as a task-specific package, not as a raw dump of
database records.

The context package should provide the information needed to answer, reason, or
choose tools, while excluding noisy metadata that can lower answer quality or
encourage hallucination.

Prefer including:

- Display names and short descriptions.
- Current facts.
- Relevant history.
- Temporal summaries.
- Association context.
- Important source wording.
- Source evidence summaries.
- Inconsistency or duplicate notes when relevant.
- LLM-facing aliases.

Avoid including:

- Raw UUIDs when aliases are available.
- Large metadata blobs.
- Internal storage fields.
- Full unrelated association lists.
- Debug data unless the task is debugging.

The question is not "what can we fit in the prompt?" The question is "what does
the model need to produce the best grounded output for this task?"

### 18. Tool Errors Must Guide The Model

Tool errors are part of the agent loop. The LLM will see them, so they should be
verbose enough to redirect the model toward a valid next action.

Good tool errors should explain:

- What failed.
- Which field or constraint caused the failure.
- Which values were accepted when useful.
- Whether the model should retry, ask the user, or stop.
- How to adjust the tool call.

Bad tool errors are vague messages such as `invalid input`, `bad request`, or
`failed`.

Example:

```text
Invalid association type: FRIEND.
Use one of: KNOWS, OWNS, PARTICIPATES_IN.
If the source describes a changing status or history, create a contextual
observation record instead.
```

Verbose errors are not only for humans. They are a control surface for agentic
behavior.

### 19. Embeddings Are Backend-Derived Retrieval Artifacts

Vector embeddings are not the source of truth and they are not model-authored
canonical summaries by default.

For retrieval-augmented generation over persistent data, the primary datastore
remains authoritative. Backend code builds deterministic, typed embedding
documents from stored records, then the vector store holds semantic lookup
vectors that point back to canonical targets.

Rules:

- Embed low-noise informative text, not raw storage payloads.
- Do not embed raw UUIDs, metadata blobs, provider traces, prompts,
  provider/runtime logs, or tool-call payloads.
- Prefer typed builders per record category over generic property dumps.
- Store exactly one primary canonical target per vector record and optional
  related targets for multi-object facts.
- Keep compatible retrieval scopes on a shared embedding configuration when one
  query embedding must search all enabled scopes.
- Use `builder_version` plus `document_checksum` to decide whether an embedding
  is stale.
- If vectorization fails after a successful write, preserve the write and record
  vectorization diagnostics. Do not make vector-store availability the authority
  for whether a fact was stored.
- Answer generation must hydrate canonical targets from the primary datastore
  after vector search. Vector hits alone are never enough grounding for
  user-visible answers.
- Semantic search must ignore orphan vector hits that do not have a matching
  operational vector record. Vector hits become usable only after backend
  hydration through the operational vector record and primary datastore.
- Retrieval responses should expose frontend/LLM-safe summaries, context
  packages, and debug traces, not raw records or raw vector-store payloads.
- Conversational queries should use hybrid retrieval when available, then
  hydrate and answer from a compact context package. The final user-visible
  response is grounded in canonical state; retrieval hits and traces are support
  metadata for tooling, debugging, and UI exploration.
- Exact/property search remains useful as a fallback and as an explicit
  workspace mode, but it should not be confused with semantic retrieval.

### 20. Separate Durable Domain Objects From Event/Observation Records

Prompts, schemas, and validators must distinguish stable domain objects from
lightweight event or observation records.

Durable domain objects are long-lived things such as people, places, events,
organizations, products, documents, accounts, cases, topics, or other domain
objects that can accumulate information over time. Event or observation records
are small dated facts, updates, corrections, or contextual notes that compose
around one or more durable objects.

Rules:

- Create or resolve a durable domain object when the text introduces something
  that can accumulate information over time.
- Create an event or observation record when the text is a short update,
  observation, correction, or contextual fact about existing or newly resolved
  targets.
- Do not create a new durable object for every small user update.
- Do not hide the full event or observation history as a JSON array inside the
  durable object.
- An event or observation record may refer to multiple involved objects,
  contexts, and media assets.
- An event or observation record may have multiple host refs, with one primary
  host used for ranking, deduplication, and default UI anchoring.
- Media attachments should be represented as media records associated through
  typed refs, not as inline attributes on unrelated records.
- Default UI should render durable objects and fold event/observation hits into
  their primary host. Detailed records can be shown in a nested timeline or
  detail view unless debugging.
- Nested history navigation should use dedicated read endpoints and backend
  filters for time, category, source, involved target, media-only, and archived
  inclusion. Selecting a durable object should preserve the current graph or
  workspace view; focusing the object's neighborhood should be an explicit UI
  action.
- Debug/UAT should expose retrieval evidence, scopes, scores, roles, and
  hydration paths in diagnostics panels before introducing raw event or
  observation graph rendering.
- Prompt examples should show the model how to choose between durable objects,
  event records, observation records, metadata patches, contextual records, and
  status records.

## Practical Development Rules

- Treat schemas, tools, and prompts as one design surface.
- Keep production prompts that affect persistent state code-managed, registry-compatible, and covered by rendering/quality tests.
- Keep model outputs structured when they affect persistent state.
- Let the orchestration layer be dynamic, but keep writes validated.
- Prefer context engineering over larger prompts.
- Build low-noise context packages for LLM answer generation and tool use.
- Build low-noise embedding documents for semantic retrieval; do not embed raw
  storage records or model/tool traces.
- Hydrate and rank vector hits through backend services before using them in
  prompts or UI responses.
- Keep durable domain objects separate from lightweight event or observation
  records in prompts, schemas, storage, retrieval, and UI rendering.
- Prefer a small strong toolbox over many vague tools.
- Add deterministic code where it is clearly cheaper, faster, and more reliable.
- Add model calls where language, ambiguity, or contextual judgment matters.
- Use short LLM-facing aliases instead of raw database IDs in prompts and tool
  schemas.
- Make tool errors actionable enough for the model to repair invalid calls.
- Record model inputs, outputs, prompt versions, schema versions, and tool calls
  when they affect persistent state.

## Design Checklist For New AI Features

Before implementing a new AI behavior, answer:

- What is the agent trying to achieve?
- Which model is appropriate for the task difficulty?
- What structured output is expected?
- Which context is necessary?
- Which context should be excluded?
- Which internal IDs need LLM-facing aliases?
- What context package shape should be sent to the model?
- Which tools are available?
- What tool errors should guide invalid or unsafe calls?
- What are the deterministic guardrails?
- What happens if the model is uncertain?
- What happens if validation fails?
- What state changes must be auditable?
- What privacy or provider constraints apply?

## Implementation Baseline

For a first implementation, these principles imply:

- Use Pydantic objects or equivalent schema objects for extraction and tool
  contracts.
- Keep the orchestration layer responsible for dynamic conversation and process
  control.
- Keep domain services responsible for structured persistence operations.
- Use external AI services initially only with provider boundaries documented.
- Support multiple input modalities through explicit source records and
  modality-specific preprocessing.
- Use LLM-facing ID aliases for stored context and tool calls.
- Keep interrupted agentic frames compact, expiring, and aligned with provider
  tool-call message history.
- Add richer deterministic handling only when real usage shows the need.
