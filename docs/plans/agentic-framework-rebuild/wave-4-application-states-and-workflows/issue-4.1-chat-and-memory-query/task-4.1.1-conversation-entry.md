# Task 4.1.1 — implement conversation-entry state

**Status: Implemented for review — effective child contracts remain in their owning tasks**

## User story

As a chat user, I want my request answered by the conversation-entry agent,
which can use explicitly configured child states or workflows as tools, so
their results are interpreted into one appropriate final response.

## What and why

Implement the root state using the generic framework, selected prompt version,
the model-history projection prepared by Task 4.1.0, and its approved toolbox.
It owns no persistence, provider loop, or domain service implementation.

## Where

- `src/product/application/states/conversation_entry/models.py` and `state.py`
  for the request DTO and concrete root state respectively.
- `src/product/application/tools/conversation_entry/models.py` and `toolbox.py`
  for temporary typed capability contracts and injected-handler composition.
- `src/product/prompts/` for the reusable exact-version prompt boundary and the
  conversation-entry template.

## Functional communication DTOs

Input: the current user request plus the caller-selected model-history
projection. Owner identity, conversation ownership, channel transport, and
durable records remain application-service/runtime dependencies rather than
model arguments. `query_memory` invokes a child state; `ingest_memory` invokes
the bound `MemoryIngestionWorkflow.ingest_memory` method. Each receives its
typed request and returns functional data as its matched tool output. Output:
final assistant text or the framework's existing awaiting-input continuation,
never raw tool JSON.

Until the two child capabilities are implemented, both tool names use one
minimal temporary request/result contract and require injected executable
functions. They provide no fake production behavior. Task 4.1.2 replaces the
query registration with `MemoryQueryState`'s reviewed contract; Task 4.3.5 does
the same for `MemoryIngestionWorkflow`.

## Dependencies and acceptance

- Depends on Task 4.1.0 and the Wave 2 base state/history. Define child tools and registrations
  from this state's reviewed behavior rather than assuming the current draft
  toolbox.
- The current user request is appended once; it is not already present in the
  selected prior-history projection.
- Bind `query_memory` when its child state exists. Bind `ingest_memory` to the
  concrete workflow method in Task 4.3.5. Until then, composition must inject
  explicit temporary handlers; the state defines no fallback handler.
- Root invocation uses the shared session and its own local transcript.
- Child-state and workflow results return to the invoking state as matched tool
  outputs; neither is rendered directly as the chat answer.
- Prompts use the documented versioned prompt lifecycle.

## Implementation checkpoint

The concrete state now renders the exact `conversation-entry:v1` file-backed
prompt, copies the caller-prepared master projection, appends the current
request once through `BaseAgenticState`, and supplies only the two accepted
capabilities. The prompt library uses an injectable `PromptTemplateSource`, so
local files and a later database source share one service and rendering
contract. Legacy chat/API wiring remains deferred until the parallel target
entrypoint is ready.
