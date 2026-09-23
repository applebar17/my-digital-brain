# Memory query state

## Purpose

`MemoryQueryState` answers a memory-dependent question from grounded graph
context. It is a composite state: deterministic retrieval and hydration happen
first, then an LLM session interprets the resulting context.

The state does not mutate graph data and does not ask the user for
clarification. When evidence is weak or ambiguous, it returns a bounded,
grounded outcome describing what is known and what is missing.

## Invocation and contracts

The state supports both direct backend invocation and use as the `query_memory`
agentic tool of `ConversationEntryState`.

```python
class MemoryQueryRequestDTO(BaseModel):
    """A user memory question to investigate with grounded graph context."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        description="The user memory question that retrieval and the state must investigate."
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

The current request is appended once as the state-local user message. Selected
master history comes from `AgenticHistorySession`; it is not copied into the
query DTO.

## Execution

```text
MemoryQueryState.invoke(request)
  -> deterministic hybrid/vector retrieval
  -> hydrate retrieved graph targets
  -> build MemoryQueryContextPacket
  -> render selected context sections and invoke main LLM session
  -> validate MemoryQueryResultPacket
```

The default main session has no toolbox. A concrete configuration may supply a
small read-only toolbox when it needs to enlarge the initial packet, such as
timeline, map, neighborhood, or evidence inspection. This is an explicit state
configuration, not automatic context expansion.

## Parent-tool behavior

When called by an LLM parent, the `query_memory` handler starts a child state
run and maps its `MemoryQueryResultPacket` to one `ToolOutputDTO` using the
parent's original provider call ID. The parent then resumes its normal provider
loop and owns any final user-facing prose.

When invoked directly by deterministic application code, the caller consumes
the result packet as context or an application result. Neither mode creates a
separate chat response protocol.

## Verification

Tests cover retrieval-before-LLM preparation, hydration, bounded no-evidence
results, no write/clarification tools, optional read-tool expansion, and exact
parent tool-call correlation.
