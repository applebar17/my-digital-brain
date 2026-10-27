# Memory query state

## Purpose

`MemoryQueryState` answers a memory-dependent question from grounded graph
context. It is a composite state: deterministic retrieval and hydration happen
first, then a tool-enabled LLM session may refine that context before producing
its grounded result.

The state does not mutate graph data and does not ask the user for
clarification. When evidence is weak or ambiguous, it returns a bounded,
grounded outcome describing what is known and what is missing.

## Invocation and contracts

The configured application capability is exposed as the `query_memory`
agentic tool of `ConversationEntryState`. Its typed state entrypoint remains
separate from provider dispatch, so another reviewed composition can invoke it
without introducing a second LLM protocol.

```python
class MemoryQueryRequestDTO(BaseModel):
    """A user memory question to investigate with grounded graph context."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        description="The memory question, doubt, or need that the state must resolve."
    )


class MemoryQueryContextPacket(BaseModel):
    """Compact hydrated retrieval context prepared before the LLM session."""

    model_config = ConfigDict(extra="forbid")
    ...  # Concrete retrieval/evidence fields are owned by the retrieval contract.


class MemoryQueryResultPacket(BaseModel):
    """Bounded grounded query result returned to the direct caller or parent tool."""

    model_config = ConfigDict(extra="forbid")
    ...  # Concrete answer/evidence fields are defined with the retrieval contract.
```

The framework projects relevant conversation history from the invoking parent
through `AgenticToolInvocationContext`. The state appends its query goal once
as its purpose-specific local user request. Neither conversation content nor
backend invocation metadata is copied into `MemoryQueryRequestDTO`.

## Execution

```text
MemoryQueryState.invoke(request)
  -> deterministic semantic search from the supplied goal
  -> hydrate a bounded first-degree graph context
  -> build and render the initial MemoryQueryContextPacket
  -> invoke the main LLM session with search_memory
  -> optionally refine search/filter/hydration through matched tool outputs
  -> validate MemoryQueryResultPacket
```

The default toolbox contains the reusable read-only `search_memory` tool. Its
deterministic service accepts a semantic query, deterministic filters, or both,
plus a bounded graph-neighborhood depth. The tool adapter owns conversion from
backend UUIDs to stable invocation-local references and never exposes storage
identifiers to the model.

The search capability owns rendering of its typed model-safe result at levels
zero through two. Level zero is compact structured context, level one is the
default readable result, and level two adds available lifecycle, alias, and
temporal detail. The caller selects the level when composing the state; prompts
and states do not implement their own search-result formatting.

The main tool loop is sufficient for iterative query reasoning. Searches are
sequential because a later query may depend on the prior result and every call
updates the shared invocation-local reference map. The default state has no
separate reasoning or planning stage. Additional read tools may be configured
later only for a reviewed need.

## Parent-tool behavior

When called by an LLM parent, the `query_memory` handler starts a child state
run and maps its `MemoryQueryResultPacket` to one `ToolOutputDTO` using the
parent's original provider call ID. The parent then resumes its normal provider
loop and owns any final user-facing prose. The child starts with the framework's
inherited conversational projection and parent linkage; it does not read global
master history independently. A deterministic composition may consume the same
typed result, but must provide its state context explicitly rather than create a
second history path.

## Verification

Tests cover retrieval-before-LLM preparation, bounded iterative search and
hydration, coherent local references, no-evidence results, absence of
write/clarification tools, and exact parent tool-call correlation.
