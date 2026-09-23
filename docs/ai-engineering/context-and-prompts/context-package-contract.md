# Context package contract

## Purpose

A context package is the typed, purpose-specific information prepared for one
LLM state or preparation call. It carries only what that call needs to reason
or act reliably; it is not a dump of database records, session metadata, or
another state's transcript.

This contract owns context construction and rendering boundaries. Prompt files
own behavior, the history session owns history selection, toolboxes own
capabilities, and domain services own retrieval and persistence.

## Context flow

```text
typed domain/retrieval/history inputs
  -> purpose-specific context DTO
  -> context renderer
  -> PromptRenderContextDTO named sections
  -> versioned system template
```

The context DTO stays typed until its dedicated renderer produces display-ready
named sections. Those sections are passed to the prompt renderer defined in
[prompt lifecycle and versioning](prompt-lifecycle-and-versioning.md). Prompt
rendering never stringifies arbitrary objects.

## Minimum contracts

Each concrete state owns its input/context/output DTOs. A minimal reusable
rendering boundary is:

```python
class ContextSectionDTO(BaseModel):
    """One named, model-readable section rendered from typed source data."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description="The exact named prompt slot this rendered section supplies."
    )
    content: str = Field(
        description="Readable, bounded text rendered from the typed source context."
    )


class ModelContextPackageDTO(BaseModel):
    """A bounded set of rendered sections for one stated purpose."""

    model_config = ConfigDict(extra="forbid")

    sections: list[ContextSectionDTO] = Field(
        description="The purpose-specific rendered sections supplied to one prompt."
    )
```

`ModelContextPackageDTO` is not a substitute for state-specific DTOs. For
example, `MemoryQueryContextPacket` and a future ingestion context packet own
their domain fields; their renderers emit the sections needed by their selected
prompt template.

## Selection rules

- Include source wording and evidence when a state must ground memory writes,
  identity decisions, contradiction review, or answers.
- Include model-facing reference inventory, readable labels, aliases, and
  concise descriptions when the state needs to refer to known objects.
- Include temporal context only when time affects the decision.
- Include owner context only as a deliberate, user-safe projection; never use
  backend owner identifiers as model-facing identity.
- Include compact hydrated retrieval context, not vector hits or raw graph
  records, for graph-dependent reasoning and answers.
- Include validation/tool feedback only when the state can use it to repair its
  next action.
- Exclude raw UUIDs, raw provider payloads, raw tool traces, backend session
  metadata, unrelated relationships, and arbitrary JSON blobs.

## History and nested state boundary

History is selected through `AgenticHistorySession`, not copied into a context
packet. A child state receives its own selected master-history projection and a
purpose-specific context package; it never receives its parent's raw provider
tool-call transcript.

When a child completes, it returns one compact typed tool output to its parent.
That output may become useful context for the next parent turn, but the child's
full reasoning, provider transcript, and tool trace do not propagate upward.

## Functional examples

| State purpose | Deterministic context preparation | Model-facing sections |
| --- | --- | --- |
| Conversation entry | Normalize the current user message and select concise chat history. | Current request and selected conversation history. |
| Memory query | Retrieve and hydrate relevant graph context before the LLM session. | User question, retrieval packet, reference inventory, and evidence where relevant. |
| Memory ingestion | Normalize source material and gather task-relevant graph context. | Source context, reference inventory, relevant existing candidates, and evidence. |
| Clarification agent | Receive supplied doubts and bounded candidate context. | Doubt packet, candidate summaries, reference inventory, and prior normalized answers. |

Concrete state documents define their own required sections. This table does
not impose an executable ingestion sequence or a generic context schema.

## Verification

Context fixtures must assert that a renderer includes the required named
sections, excludes backend-only fields, preserves supplied model-facing refs,
and produces readable output for the selected prompt version.
