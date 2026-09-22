# Client-runtime rebuild plan

## Goal

Replace the currently fragmented AI tool/runtime boundaries with one
provider-neutral, DTO-first implementation. The replacement must preserve the
stable application-facing capability (`run_session`, provider routing,
structured output, embeddings, transcription, and resumable clarification)
while removing incorrect or duplicated tool-loop logic.

The replacement follows the repository's binding
[dependency-oriented module design](../../requirements/technical/dependency-oriented-module-design.md).
The runtime's code should therefore be readable from contracts and protocols,
through helpers and base abstractions, to concrete adapters, orchestration, and
finally the composition boundary. Important runtime methods must document their
immediate collaborators and material side effects.

This is a migration plan, not authorization to run multiple production client
frameworks indefinitely.

## Current inventory

| Area | Current responsibility | Migration treatment |
| --- | --- | --- |
| `ai/client/` | SDK setup, request compatibility, retry/context helpers | Keep only reviewed SDK/configuration concerns behind an adapter boundary. |
| `ai/providers/openai.py` and `azure_openai.py` | Chat Completions translation, metadata, `run_session` entry | Replace translation with DTO normalization; preserve provider capability and route ownership. |
| `ai/session/` | Session DTOs, loop, continuation, tool executor | First replacement target; this becomes the one canonical runtime. |
| `ai/router.py` | Task-to-model/deployment route | Preserve as a separate typed routing concern. |
| `agentic/runtime_state.py` | Builds application-specific state calls on top of sessions | Migrate after session contracts are stable; it must not own provider transcript repair. |
| `ai/ai_clients/` | Imported reference implementation | Reference-only until deliberately migrated and made standalone; never run in parallel with the active stack. |

## Required decision before implementation

Choose one provider API baseline for the initial canonical adapter:

1. **Chat Completions baseline**: retain the current OpenAI/Azure compatible
   endpoint and normalize its assistant `tool_calls[].id` as `provider_call_id`.
2. **Responses baseline**: adopt Responses as the primary OpenAI protocol and
   normalize `function_call.call_id` as `provider_call_id`; Azure support must
   be confirmed for the selected deployment/API version before this option is
   implemented.

The runtime contract stays identical under either option. The decision changes
only adapter implementation and test fixtures. Do not mix endpoint-specific
message formats in one transcript.

## Migration waves

### Wave 0 — Lock contracts and executable invariants

Create canonical Pydantic DTOs for provider completion, tool call, tool output,
tool error, registered tool definition, session request, session result, and
continuation. Generate provider tool schemas from input DTOs. Write contract
tests before moving callers.

Exit criterion: tests prove one output per provider call ID, including errors,
batch calls, nested agent tools, and clarification pause/resume.

### Wave 1 — Rebuild the generic session loop

Implement an iterative, append-only transcript loop with no domain-specific
branches. The loop may execute, pause, complete, or fail according to
[the protocol](../runtime/tool-calling-protocol.md). It does not know graph
labels, ingestion states, clarification wording, or UI response formatting.

Exit criterion: fake transport tests cover every runtime terminal state and no
tool payload can populate the completed assistant content.

### Wave 2 — Migrate provider adapters

Implement the selected OpenAI/Azure adapter against the Wave 0 DTOs. The
adapter serializes and parses only the selected provider protocol, retains
request IDs/usage as diagnostics, and normalizes provider tool-call IDs.

Exit criterion: adapter conformance fixtures cover plain final text, one tool
call, multiple calls, malformed arguments, provider failure, and tool output
round-trip.

### Wave 3 — Migrate tool registration and application tools

Replace loose mappings and keyword handlers with typed `ToolDefinition`
registrations. Each application tool receives `ToolContext` plus an input DTO
and returns an output DTO. LLM-backed tools use the same outer contract and
compact their child session result.

Exit criterion: agentic and clarification tools have no untyped dispatch
boundary and no duplicate tool-output writer.

### Wave 4 — Migrate consumers and continuations

Move `agentic/runtime_state.py`, chat, ingestion, and clarification persistence
to the canonical session/continuation DTOs. Keep an adapter only while each
consumer moves; delete it immediately after its last caller is migrated.

Implement `BaseAgenticState` only after the canonical session loop and typed
toolbox registration exist. Migrate one concrete state at a time using the
[agentic state framework](../runtime/agentic-state-framework.md); it must
delegate to the canonical client runtime rather than retaining a second
conversation/tool loop.

Introduce the shared
[AgenticHistorySession](../runtime/agentic-history-session.md) with the base
state migration. It replaces loose metadata-backed master histories and keeps
parent/child state-local transcripts separate; do not retain a parallel history
path after a caller has moved.

Exit criterion: one end-to-end ingestion with a real tool failure and a
clarification pause resumes the same transcript correctly.

### Wave 5 — Remove superseded implementation

Delete unused session helpers, compatibility paths, old dispatch code, and any
copied reference code that was not intentionally ported. Remove stale tests and
documentation in the same wave.

Exit criterion: one importable AI runtime, one provider adapter boundary, one
tool registration path, and no compatibility code whose caller no longer
exists.

## Non-negotiable acceptance criteria

- All cross-boundary payloads are explicitly typed Pydantic DTOs.
- Tool handlers do not accept undeclared `**kwargs` as their application
  contract.
- A provider-issued call ID is never generated, replaced, or paired twice by
  application code.
- Successful, recoverable, and unexpected tool failures all re-enter the
  invoking model session through one matched output.
- A child agent is a normal tool from its parent's perspective.
- A final chat response comes only from a terminal assistant completion or a
  user-safe API error renderer, never from a tool result.
- Each migration wave is independently tested and committed.
