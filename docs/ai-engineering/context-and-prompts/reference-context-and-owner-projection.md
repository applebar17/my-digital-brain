# Reference context and owner projection

## Purpose

`ReferenceContext` is the typed, run-scoped bridge between persisted domain
objects and the readable references an LLM may use during one workflow or
agentic-state invocation. It lets states refer to the same objects coherently
without exposing backend UUIDs, storage records, or provider identifiers.

The context is part of a state-specific context package. It is not history, a
graph query API, or a global identity registry.

## Reference entry boundary

Each reference entry has a model-facing identifier and a private backend
mapping. The model-facing projection contains only the information needed to
identify and reason about the object: its reference, object kind, label,
readable name or summary, useful aliases, and its current resolution state.

```text
model-facing reference <-> ReferenceEntry <-> private persisted identifier
```

The backend creates and resolves the mapping. A model may select only a
reference supplied in its current context; it never receives or creates the
persisted identifier.

The model-facing entry is a DTO with explicit semantic fields, rather than an
arbitrary property bag:

```python
class ReferenceObjectKind(str, Enum):
    """Object categories represented in a workflow reference context."""

    NODE = "node"
    MEMORY_LOG = "memory_log"
    RELATIONSHIP = "relationship"
    CONTEXT = "context"
    MEDIA = "media"
    CANDIDATE = "candidate"


class ReferenceResolutionStatus(str, Enum):
    """Lifecycle position of a referenced object in the active workflow."""

    EXISTING = "existing"
    PROPOSED = "proposed"
    CREATED = "created"


class ReferenceEntryDTO(BaseModel):
    """One model-safe object reference available in the current workflow."""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(
        description=(
            "Backend-issued model-facing reference for this active workflow. "
            "Use this exact value when another DTO or tool requires the object."
        )
    )
    object_kind: ReferenceObjectKind = Field(
        description="Domain object category represented by this reference."
    )
    label: str | None = Field(
        description="Graph label or domain type when it helps identify the object."
    )
    display_name: str | None = Field(
        description="Readable object name when one is available."
    )
    summary: str | None = Field(
        description="Brief user-meaningful description when a name alone is insufficient."
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known useful alternate names; omit unrelated or speculative aliases."
    )
    resolution_status: ReferenceResolutionStatus = Field(
        description="Whether the object is existing, proposed, or created in this workflow."
    )
```

The private mapping is deliberately absent from this DTO. It belongs to the
backend reference service, which validates the ref and resolves its persisted
identity only when a deterministic tool needs it.

References are unique for the active workflow run. A child state receives the
relevant reference context from its caller and returns only a compact reference
delta when it creates or resolves objects. The parent merges that typed delta
before invoking the next dependent state.

## Reference allocation conventions

The backend issues predictable run-scoped references for ordinary graph
objects. The active baseline is `node_0001` and `node_new_0001` for existing
and proposed nodes, with equivalent `memory_`, `edge_`, `context_`, and
`media_` families. A candidate created for the identity-lookup handoff uses a
`candidate_<kind>_0001` family. The exact counter has no meaning beyond
uniqueness in the active workflow.

The owner packet is the intentional exception: it uses its safe readable
`name_surname` identifier or `owner` fallback. It still participates in the
same private mapping and reference validation boundary as every other entry.

## Owner packet

The owner is projected explicitly whenever first-person language or owner
relationships are relevant. It is a model-facing context object, not a backend
user ID and not a hard-coded universal graph identifier.

```python
class OwnerContextDTO(BaseModel):
    """The active workflow owner's safe identity projection for an LLM context."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        description=(
            "Readable model-facing owner reference. Build it from the available "
            "name and surname, for example 'jacopo_brutti'; use 'owner' when "
            "either identity value is unavailable. It is not a backend UUID."
        )
    )
    name: str | None = Field(
        description="Owner's given name when safely available to this context."
    )
    surname: str | None = Field(
        description="Owner's surname when safely available to this context."
    )
```

`id` is built deterministically by the backend from the active owner's safe
projection. It is `name_surname` when both values are available and `owner`
otherwise. The backend privately maps this reference to the actual owner node
or user identity for the current workflow. The LLM must use the supplied owner
`id` when referring to the owner in structured objects or tool arguments.

The packet is rendered as a named context section, for example:

```text
Current owner:
- `jacopo_brutti` refers to Jacopo Brutti.
```

An owner with no safely available name is rendered without inventing one:

```text
Current owner:
- `owner` refers to the current owner.
```

## Rendering levels

`ReferenceContext` provides one rendering function with an explicit verbosity
level. The renderer, rather than each prompt or tool, owns this presentation so
the same reference has the same meaning throughout one workflow.

| Level | Use | Rendering |
| --- | --- | --- |
| `0` | Structured/debug-oriented exchange where compact fields are sufficient. | Plain ref, object kind, label, and name or summary. |
| `1` | Default for state prompts and normal tool guidance. | A short natural-language statement such as `` `node_0001` refers to the Person 'Jacopo Brutti'. `` |
| `2` | A state needs additional purpose-specific guidance, such as identity resolution. | Level 1 plus selected aliases, resolution status, relevant relationship/time/source hints, and an explicit note on how the ref may be used. |

Level 2 adds only facts already present in the typed entry. It must not invent
instructions, semantic decisions, or object relationships. A caller chooses
the level deliberately; level 1 is the baseline.

## Context selection and safety

- Include only references useful to the receiving state and its declared task.
- Include names, concise summaries, aliases, and selected evidence or temporal
  hints only when they help a real decision.
- Keep candidate lookup results clearly identified as evidence, not as an
  automatic binding or duplicate decision.
- Do not expose UUIDs, raw graph records, vector IDs, audit metadata, raw tool
  traces, or unrelated private context.
- A deterministic lookup service may build bounded candidate entries. It is a
  backend capability; the workflow and state decide when its result is needed.
- Unknown, stale, or out-of-scope model references produce one actionable tool
  error for the invoking state to handle. They do not cause an implicit create,
  merge, or workflow break.

## Integration points

- [Context package contract](context-package-contract.md) owns placement of a
  rendered reference section inside a purpose-specific model context package.
- The deterministic ingestion workflow owns passing the evolving context and
  typed reference deltas between dependent states.
- State DTOs name the reference fields they accept and describe their expected
  object kinds; deterministic tools resolve the private mapping at execution.
- The provider tool-call protocol owns continuation after a tool result; a
  reference error remains a normal tool output, never a chat final response.

## Verification

Fixtures should prove that the same entry renders consistently at levels 0, 1,
and 2; that the owner fallback is `owner`; that backend IDs never reach the
rendered result; and that a child-state delta is visible to its next dependent
state without exposing the child transcript.
