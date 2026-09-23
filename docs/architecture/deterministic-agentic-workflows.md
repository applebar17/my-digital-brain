# Deterministic agentic workflows

## Purpose

A deterministic agentic workflow coordinates a known sequence of agentic
states for one application capability. It is deterministic about execution
order, dependency handoff, and context propagation. It is not deterministic
about the semantic judgments made inside an LLM state.

This is the MVP orchestration approach. A future agent-to-agent coordinator may
replace the workflow scheduler, but it must preserve the same state entrypoints,
DTO contracts, tool protocol, history behavior, and reference-context boundary.

## Workflow responsibility

A `Workflow` class has one narrow responsibility: invoke explicitly configured
states in dependency order and pass their typed compact outputs to the next
state. It owns:

- the workflow input and final-result DTOs;
- declared state order and input/output dependencies;
- deliberately approved parallel work where sibling states have no data
  dependency;
- the selected history projection, evolving `ReferenceContext`, and compact
  prior-state results provided to each state;
- a pause/resume boundary when a state asks a clarification through the normal
  provider tool protocol.

It does not interpret LLM output, perform graph writes, infer missing graph
objects, parse prose into DTO fields, hide tool failures, or carry raw provider
traces between states.

## State handoff contract

Every workflow state receives a typed input DTO and returns a typed compact
result DTO. The result contains only the semantic output required by a
dependent state, plus an optional typed reference-context delta. Raw history,
provider responses, tool-call identifiers, and backend identifiers stay with
their owning runtime/service boundaries.

```text
workflow input + selected history + ReferenceContext
  -> state input DTO
  -> agentic state / deterministic service
  -> compact state result DTO + ReferenceContext delta
  -> next dependent state input DTO
```

The workflow merges a valid reference delta before preparing the next state.
It does not create a second alias convention or expose private mappings.

## Initial memory-ingestion workflow

The current ingestion design is intentionally phased because later objects
depend on earlier resolved objects. The workflow is:

```text
source normalization, retrieval, and context preparation
  -> ingestion reasoning state
  -> node candidate state
  -> deterministic identity lookup and candidate-context preparation
  -> node resolution/write state
  -> memory/context ingestion state
  -> relationship ingestion state
  -> compact ingestion workflow result
```

The preparation step is deterministic: it normalizes the source, retrieves and
hydrates bounded graph context, builds `ReferenceContext`, and adds the active
owner projection when relevant. It does not decide what the source means.

The reasoning state produces a structured, non-executable interpretation that
may identify salient entities, aliases, ambiguities, likely durable
relationships, and details that should not become durable graph objects. It
does not allocate persisted IDs or make graph writes.

The node candidate state identifies structured candidate objects from the
reasoning artifact. It does not form a graph query, choose matching policy, or
write to the graph. The workflow then invokes a deterministic lookup service
for every candidate whose object kind has configured identity lookup. That
service derives its own lookup request, returns bounded candidate evidence, and
adds supplied existing-object references to the `ReferenceContext`.

The node resolution/write state receives the candidate and its lookup evidence.
It may choose an explicitly supplied existing reference, create a new object,
or ask clarification. Lookup evidence is not an automatic binding, merge,
rejection, or clarification decision. Valid node results make their newly
created or resolved references available to later dependent states.

The memory/context state runs before relationship work when a relationship must
be linked to a context or perception object. The relationship state uses
references made available by the previous successful state results; it does not
use unresolved natural-language names as endpoints.

This order is a dependency contract, not an instruction to suppress a valid
clarification, fabricate a missing object, or make a semantic decision without
the LLM. A state may use its configured tools, including clarification, within
the provider continuation protocol.

## Identity lookup and additive updates

Identity lookup is a deterministic backend capability within the workflow. It
owns normalization, allowed object kinds, bounded search, candidate
classification, graph access, redaction, and model-safe candidate packet
construction. The LLM receives the resulting packet as evidence only; it never
produces Cypher, persisted IDs, or an executable graph search.

When a supplied existing reference is selected, the normal default is additive:
the workflow may create a source-backed memory, supported relationship, claim,
perception, or context record against that reference. It must not silently
overwrite identity properties merely because a lookup found a plausible match.
An explicit, typed property-update contract is required for any direct update.

The same principle applies after clarification. A user answer enriches the
resumed state context; the agent must return the corrected value in its typed
result or tool arguments. Backend code never extracts a graph field from the
answer prose or explanation field.

## Clarification and errors

If a state invokes clarification, its open provider call is paused. The user
answer becomes the single matched tool output for that call, and the same state
resumes with its preserved state history, typed context, and reference context.
The workflow does not create a parallel clarification stage or reroute the
request to a different state.

If a deterministic tool or child state fails, the caller receives one compact,
actionable tool output and may respond, retry with corrected DTO arguments, ask
clarification, or return a partial semantic result. The workflow receives the
eventual state result; it must not turn the tool result itself into a user-facing
chat answer or terminate the caller chain.

## Parallelism

Parallel execution is allowed only where a workflow definition explicitly
declares sibling tasks context-independent. A task that creates or resolves a
reference required by another task is sequential by definition. The initial
ingestion workflow therefore preserves node, memory/context, and relationship
dependencies. It makes no premature promise to parallelize those states.

## Future replacement boundary

If the product later adopts agent-to-agent delegation, only the coordination
policy changes. Each state still exposes the same `BaseAgenticState` entrypoint,
accepts typed input/context, uses its configured toolbox, and returns a compact
result. The new coordinator must obey the same history, reference, tool-output,
and error-continuity contracts.

## Related documentation

- [Agentic state framework](../ai-engineering/runtime/agentic-state-framework.md)
- [Agentic history session](../ai-engineering/runtime/agentic-history-session.md)
- [Tool-calling protocol](../ai-engineering/runtime/tool-calling-protocol.md)
- [Reference context and owner projection](../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
- [State and tool taxonomy](../ai-engineering/application-states/state-and-tool-taxonomy.md)
