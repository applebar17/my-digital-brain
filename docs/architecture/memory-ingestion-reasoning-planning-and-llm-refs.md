# Memory Ingestion Reasoning, Planning, And LLM-Facing Refs

## Purpose

This document locks the next ingestion architecture enhancement after the
frame-based agentic runtime cleanup.

The problem being addressed is source collapse: a dense memory can currently be
stored as a small number of oversized memories with too few durable graph
relationships. The target model separates:

- reasoning about durable nodes;
- reasoning about source-backed memories;
- reasoning about edges and context links across those objects;
- deterministic backend reference mapping and graph writes.

The core mantra is:

```text
consistent LLM-facing refs down, backend truth underneath, compact refs up
```

LLM-facing states should work with readable refs such as `node_0001`,
`memory_0003`, and `edge_0002`. Backend services own the mapping between those
refs and persistent graph identifiers.

## Locked Decisions

- LLM-facing states should not reason over raw backend UUIDs by default.
- Hydrated graph objects receive stable session-local refs before being shown to
  an LLM.
- Newly proposed objects receive provisional session-local refs before they are
  written.
- The backend owns the session ref map and validates every tool call by
  resolving refs before graph mutation.
- Local refs are stable for the lifetime of the frame/session context. A
  provisional ref such as `node_new_0001` should not be renamed after write; it
  should be updated with its backend id in the ref map.
- Edge planning must reference known local refs, not loose names or aliases.
- Node, memory, and edge planning should be separate phases guided by a shared
  structured reasoning artifact.
- Tool arguments, tool descriptions, output schemas, prompts, and tool results
  should consistently use LLM-facing refs. Tool summaries should speak back in
  refs, for example `node_0001 updated`, `node_new_0002 created`, or
  `memory_0004 linked to node_0001`.
- Raw backend ids may remain in diagnostics, audit payloads, and storage, but
  they should not be visually dominant in prompts, model-facing context, or
  ordinary tool summaries.
- Nodes, memories, edges, media, and context records sent to LLM-facing states
  must be converted into minimal LLM-friendly packets. Non-essential storage,
  audit, trace, backend metadata, raw payloads, timestamps unrelated to the
  reasoning task, and duplicate fields should be removed before the model sees
  them.
- Each implementation wave must keep the affected code clean. When a new
  contract, tool, packet builder, prompt path, or orchestration path replaces an
  older behavior, update the existing code in place and remove or quarantine the
  deprecated path in the same wave whenever practical. Prefer visible failures
  over hidden legacy fallback behavior. Do not keep wrappers, compatibility
  branches, unused prompt fragments, unused tool handlers, or duplicate model
  shapes unless a current public API, migration, or test explicitly requires
  them.

## Implementation Hygiene

The architecture should be implemented with cleanup as part of every step, not
as a vague final task. The expected rule is:

```text
new path in, obsolete active path out
```

For every wave:

- update the current affected implementation rather than layering a parallel
  production path beside it;
- remove model-visible legacy tools, prompts, routing branches, and tests once
  the replacement is active;
- keep migration-only or API-compatibility code inert, clearly named, and out of
  model-visible/runtime orchestration;
- avoid hardcoded `None` fields, placeholder output fields, and legacy schema
  remnants when the field is no longer semantically used;
- keep tool schemas, context contracts, prompt builders, and tests aligned with
  the actual runtime behavior;
- prefer failing visibly with structured diagnostics over silently falling back
  to an older orchestration path;
- keep logs and tool results compact, ref-based, and free from prompt/raw trace
  noise unless an explicit debug flag is enabled.

## LLM-Friendly Packets

Model-facing packets should be deliberately small. The goal is to give the LLM
enough information to reason, plan, and reference objects consistently without
forcing it to parse backend storage details.

For every hydrated or newly created object, the backend should produce a compact
packet shaped around:

- `ref`;
- object kind and label/type;
- human-readable name or short summary;
- aliases or role names only when useful;
- relationship endpoints as refs;
- relevant time/place/source hints;
- selected source hints when useful, without requiring source spans in the core flow;
- ambiguity or resolution status when it affects planning.

Packets should exclude by default:

- raw backend UUIDs;
- storage-only metadata;
- audit fields;
- prompt traces;
- vector ids and collection internals;
- raw source payload dumps;
- duplicate serialized versions of the same object;
- large property bags when only a label, name, summary, or selected fields are
  needed;
- unrelated timestamps or lifecycle fields unless the current reasoning task
  needs them.

Example node packet:

```json
{
  "ref": "node_0001",
  "kind": "node",
  "label": "Person",
  "name": "Marco Bianchi",
  "aliases": ["Marco"],
  "resolution_status": "existing",
  "why_relevant": "Possible endpoint for this memory."
}
```

Example memory packet:

```json
{
  "ref": "memory_0003",
  "kind": "memory_log",
  "summary": "The user played Bang Duel with Merc and Bri at the beach.",
  "primary_host_ref": "node_0001",
  "involved_refs": ["node_0007", "node_0008"],
  "time_hint": "Republic Day afternoon",
  "source_hint": "user message"
}
```

Example edge packet:

```json
{
  "ref": "edge_0002",
  "kind": "relationship",
  "from_ref": "node_0001",
  "to_ref": "node_0004",
  "relationship_type": "BROTHER_OF",
  "summary": "Lorenzo is the user's brother."
}
```

If a tool needs backend ids, the backend resolves refs internally. The model
should not need to see those ids to plan correctly.

## Packet Detail Profiles

Packet builders should support explicit detail profiles so each state receives
only what it needs.

- `short`: `ref`, kind/label, and name/title only. Use for compact lists,
  selection menus, and allowed-ref reminders.
- `medium`: `ref`, kind/label, name/title, compact summary, and the few key
  aliases, time hints, place hints, or endpoint refs needed for reasoning. This
  is the default for ingestion reasoning and planning.
- `long`: medium packet plus selected related refs, relevant recent logs/context,
  and selected source/context hints. Use only when a state needs richer local context
  for ambiguity resolution or a specific planning decision.

The default ingestion packet profile is `medium`: id/ref + name + summary, with
minimal linking hints.

Wave 1 starts with enum-only packet profiles. Contract and function signatures
should leave room for future state-specific packet overrides, but the first
implementation should not add override behavior until a concrete state needs it.

## Ref Context

Every agentic frame that reasons about graph objects should carry a
`ref_context`.

The internal `ref_context` may store backend ids so tools can resolve refs to
persistent graph objects. The model-facing `ref_context_packet` should expose
only refs, object kind, label/type, names, summaries, aliases, and resolution
status by default. Backend ids should appear only in diagnostics or explicit
debug views.

Conceptually:

```text
Model ref     <->  frame/session ref map        <->  backend truth
node_0001     <->  object ref entry             <->  graph node UUID
memory_0003   <->  object ref entry             <->  MemoryLog UUID
edge_0002     <->  object ref entry             <->  relationship id/key
context_0001  <->  object ref entry             <->  Claim/Perception/etc id
media_0001    <->  object ref entry             <->  MediaAsset id
```

Internal ref-map entry:

```json
{
  "ref": "node_0001",
  "object_kind": "node",
  "label": "Person",
  "display_name": "Marco Bianchi",
  "backend_id": "node_19834uh98fn983948",
  "resolution_status": "existing",
  "source": "hydrated_context",
  "aliases": ["Marco"]
}
```

Internal provisional ref-map entry:

```json
{
  "ref": "node_new_0001",
  "object_kind": "node",
  "label": "Person",
  "display_name": "Lorenzo Tordini",
  "backend_id": null,
  "resolution_status": "proposed",
  "source": "node_planning",
  "aliases": ["Lorenzo"]
}
```

After write, the same `ref` is retained and the backend id is filled:

```json
{
  "ref": "node_new_0001",
  "backend_id": "node_7b4d...",
  "resolution_status": "created"
}
```

## Ref Naming Rules

Use a small set of predictable prefixes:

- `node_0001`: existing hydrated domain or context node.
- `node_new_0001`: proposed node not yet persisted when first introduced.
- `memory_0001`: existing hydrated `MemoryLog`.
- `memory_new_0001`: proposed `MemoryLog`.
- `edge_0001`: existing hydrated relationship or edge-like link.
- `edge_new_0001`: proposed relationship.
- `context_0001`: existing hydrated context record such as `Claim`,
  `Perception`, `RelationshipContext`, `RelationshipState`, or
  `ProfileMemory`.
- `context_new_0001`: proposed context record.
- `media_0001`: existing hydrated media/source asset.
- `media_new_0001`: proposed media/source asset when needed.

Rules:

- In this document, a session means one full memory ingestion run from reasoning
  through planning and write completion. When that ingestion completes, the next
  memory ingestion starts a fresh ref session and may reuse refs such as
  `node_0001`.
- Counters are allocated by the backend, not by free-form prompt convention.
- Refs are unique within the active ingestion session ref context.
- Child frames inherit the parent ref context relevant to their work.
- Child frames may add refs; completion compacts those additions back to the
  parent.
- Tools reject unknown refs unless the tool explicitly creates a new ref in an
  allowed creation phase. Tool argument descriptions, output-schema
  descriptions, and state prompts must make this rule explicit where refs are
  accepted.
- Edge endpoints must resolve to known node/context refs before write.

## Context Propagation And Packet Labels

Nested agentic execution follows the runtime mantra from the frame architecture:

```text
history and minimum sufficient context down, compact tool results up
```

As the runtime moves deeper into nested states, it carries the relevant message
history and adds only the minimum sufficient structured context for the next
state. As nested states complete, they return compact summaries as tool outputs
to the parent tool call. When a new agentic session starts, the backend rebuilds
the prompt context from history, current task, ref context, and the specific
packets that are useful for that state.

Any raw or compact packet passed to an LLM-facing state must be clearly labeled
in natural language. Do not pass anonymous JSON blobs. The prompt/context should
explain what each packet is and how the model should use it.

Examples:

```text
Previous step results:
{compact_step_result}
```

```text
Irrelevant details from this memory that should usually be ignored:
{irrelevant_details}
```

```text
Possible aliases and nickname hints to use before creating duplicate nodes:
{possible_aliases}
```

```text
Existing graph candidates that may match source mentions:
{duplicate_candidate_packets}
```

Packet labels should be short, direct, and task-specific. The packet itself
should remain LLM-friendly: refs, names, summaries, useful aliases, compact
status, and selected diagnostics only.

## State Context Contracts

### Reasoner Context

The reasoner receives:

- message history up to the current ingestion request;
- system prompt with ingestion reasoning rules;
- compact hydrated graph packet built from retrieval results;
- medium-profile packets for relevant existing nodes, memories, edges, context
  records, media/source refs when useful;
- current `ref_context` for hydrated objects only.

The reasoner produces high-level guidance. It does not create refs or executable
actions.

Expected reasoner context shape:

```text
System prompt:
  You are identifying high-level memory ingestion highlights.
  Do not create refs. Do not produce write actions.

Hydrated graph context packet:
  {medium_graph_packets}

Conversation/history:
  {message_history}
```

### Planner Context

Each planner receives:

- message history up to the current ingestion request;
- system prompt with phase-specific planning rules;
- reasoner guidance for that phase;
- `possible_aliases` packet;
- `irrelevant_details` packet;
- current `ref_context`;
- graph-related packets useful for distinguishing create, update, resolve, and
  no-op decisions;
- duplicate candidate packets when available;
- prior phase compact results when they are relevant to the current phase.

Aliases are essential for node planning. They should be rendered as a dedicated
packet with explicit guidance before node creation is attempted.

Example planner packet labels:

```text
Reasoner guidance for node planning:
{reasoning.highlights.nodes}

Possible aliases and nickname hints:
{possible_aliases}

Irrelevant details to avoid turning into nodes or edges:
{irrelevant_details}

Existing graph candidates and possible duplicates:
{duplicate_candidate_packets}

Current refs available for this planning phase:
{ref_context_packet}
```

The planner owns concrete action structure and ref creation. It may create
`node_new_*`, `memory_new_*`, `context_new_*`, or `edge_new_*` refs according to
its phase.

### Graph Ingestor / Action Context

Creation and update actions run in graph-ingestor/action frames. These frames
receive:

- relevant message history;
- system prompt with deterministic write-tool rules;
- current `ref_context`;
- aliases, irrelevant details, duplicate candidates, and prior phase summaries
  only when useful for the current action;
- one current action to achieve as the latest user message.

The current action should be appended as the final user message in
human-friendly text so the model focuses on the immediate task.

Example:

```text
System prompt:
  You execute exactly one graph ingestion action using deterministic tools.
  Use refs, not raw backend ids. Respect aliases and irrelevant-detail guidance.

Possible aliases:
{possible_aliases}

Irrelevant details to avoid:
{irrelevant_details}

Current refs:
{ref_context_packet}

User message:
  Now do this: create node node_new_0001 as Person Lorenzo Tordini. Use aliases
  Lorenzo and mio fratello. Check possible duplicates before writing.
```

The action frame may call deterministic write tools, helper read tools, or
clarification tools. It returns one compact action result to the parent.

## Reasoning Output

The first ingestion reasoning pass should produce structured reasoning guidance,
not executable graph actions and not new refs. It should identify the major
highlights of the source in mostly free-text fields so the planner receives rich
context without inheriting premature structure.

Reasoning is allowed to talk about likely nodes, memories, and edges in natural
language. It should not allocate `node_new_*`, `memory_new_*`, or `edge_new_*`
refs. Ref creation starts in planning, where duplicate context and executable
action shape are available.

```text
MemoryIngestionReasoning
  highlights
    nodes
      persons: text
      places: text
      events: text
      social_circles: text
      topics_or_objects: text
      other: text
    logs: list[text]
    edges
      family: text
      relationships: text
      perception_or_affect: text
      event_place_links: text
      other: text
  possible_aliases: object
  irrelevant_details: list[text]
  ambiguities: text
  duplicate_or_resolution_notes: text
  missing_context_questions: list[text]
  planning_guidance: text
```

Example:

```json
{
  "highlights": {
    "nodes": {
      "persons": "The main people are Lorenzo Tordini, Gianluca Ripari, Diego Cardu, Amos, Gabriele, Alessio, Giulio Zega, Jacopo Galletta, Merc, Bri, Fabione, Alessia, Elena, and Matteo Morichetti.",
      "places": "The main places are the home barbeque setting, the beach/Moon area, and Bar Mario.",
      "events": "The source describes a Republic Day barbeque, an afternoon beach outing, a Bang Duel game, and a quiet evening.",
      "topics_or_objects": "Bang Duel, rope/boxing training, and the personal memory project may be relevant as objects or topics only if useful for retrieval."
    },
    "logs": [
      "Connected to Lorenzo there is a barbeque he organized with friends and Gianluca's group.",
      "Connected to the user there is a personal project, training, cooking, beach, game, beer, and quiet evening sequence.",
      "Connected to the Moon/beach outing there is a perception that the atmosphere was not great."
    ],
    "edges": {
      "family": "Lorenzo is the user's brother. Gianluca is the user's cousin.",
      "relationships": "Alessia appears to be Fabione/Riccardo Cau's girlfriend. Elena has a boyfriend named Matteo Morichetti.",
      "perception_or_affect": "The user perceived the Moon/beach atmosphere as not great.",
      "event_place_links": "The barbeque, beach outing, Bang Duel game, and Bar Mario movement may need event/place anchoring."
    }
  },
  "possible_aliases": {
    "Lorenzo Tordini": ["Lorenzo", "mio fratello"],
    "Gianluca Ripari": ["Gianluca", "nostro cugino"],
    "Matteo Mercoldi": ["Merc"],
    "Andrea Bricca": ["Bri"],
    "Riccardo Cau": ["Fabione", "il fabione"]
  },
  "irrelevant_details": [
    "Do not create durable edges from incidental co-presence at the barbeque or beach.",
    "Do not create durable nodes for every small action unless useful for retrieval."
  ],
  "ambiguities": "Some nicknames need resolution: Merc, Bri, and Fabione should be checked against existing graph context before creating duplicates.",
  "duplicate_or_resolution_notes": "Investigate whether short names or nicknames already map to existing people.",
  "missing_context_questions": [],
  "planning_guidance": "Split this source into multiple compact memories. Avoid turning every co-presence into a durable edge."
}
```

### Reasoning Boundary

The reasoner should:

- summarize important candidate nodes in text;
- summarize memory/log highlights in text;
- summarize likely durable edges in text;
- call out ambiguity and duplicate risks;
- identify possible aliases and nickname mappings;
- identify irrelevant details that later states should usually ignore;
- preserve useful details that a strict extractor might otherwise miss.

The reasoner should not:

- allocate new refs;
- produce executable create/update actions;
- decide final duplicate resolution;
- decide final MemoryLog boundaries;
- call write tools.


Uncertainty does not deterministically block the process. The model/tool loop may
choose to create, retry with corrected arguments, no-op, ask clarification, or
return a partial result based on available context and tool feedback.

## Planning Phases

Reasoning and planning are separate.

The shared reasoning artifact guides planning and should be carried as augmented
context into each planning phase. Planning owns concrete refs, duplicate checks,
action shapes, and execution order.

```text
semantic retrieval + hydration
-> assign refs to hydrated objects
-> build medium LLM-friendly packets
-> structured reasoning guidance, without new refs
-> node planning creates/uses refs and checks duplicates
-> node execution/resolution updates ref_context and compact node result
-> memory planning uses reasoner guidance + aliases + irrelevant details + node result
-> memory execution updates ref_context and compact memory result
-> edge planning uses all useful prior results and creates refs against resolved endpoints
-> edge execution updates ref_context
-> compact result
```

### Node Planning

Input:

- reasoning highlights for nodes;
- hydrated context packets;
- possible duplicate packets from retrieval/resolution helpers;
- current `ref_context`.

Output:

- create-node actions with new refs such as `node_new_0001`;
- update-node actions against existing refs such as `node_0001`;
- resolve-existing/no-op actions when a source mention maps to an existing node;
- duplicate-risk diagnostics when the planner cannot confidently choose create
  vs existing;
- clarification requests only when identity is unsafe to infer.

Node planning is the first phase that may introduce `node_new_*` refs. The
backend validates generated refs for format, uniqueness, object-kind prefix,
and collision with hydrated refs before any write.

Node execution updates the ref map with created or resolved backend ids.
### Memory Planning

Guideline: one MemoryLog should contain one coherent observation, episode, or
state change. Long source text should produce multiple compact MemoryLogs unless
it is truly one atomic event. Prompts should include few-shot examples that show
large sources being split into node, memory, and edge plans.

Input:

- reasoning highlights for memories/logs;
- resolved node refs;
- hydrated context;
- current `ref_context`.

Output:

- create `MemoryLog`;
- create context record such as `Perception` or `Claim`;
- attach host/involved/context/media refs;
- update existing context only when clearly required.

Memory planning is the first phase that may introduce memory_new_* or
context_new_* refs. Memory execution updates the ref map with created
memory/context backend ids.

### Edge Planning

Input:

- reasoning highlights for likely durable edges;
- resolved node refs;
- created memory/context refs;
- possible duplicate relationship/context packets from retrieval helpers;
- current `ref_context`.

Output:

- create or upsert relationships using refs only;
- create relationship states through the deterministic relationship-state
  service;
- link MemoryLogs/context records to domain anchors;
- no-op diagnostics for weak co-presence that should remain MemoryLog
  involvement instead of durable graph structure.

Edge planning is the first phase that may introduce `edge_new_*` refs. It must not use unresolved natural-language endpoint names. Endpoint fields must reference local refs such as `node_0001` and `node_new_0001`.

## Step Execution Semantics

Plans are step-based. Each step contains one or more actions.

```text
Plan
  step_0001, execution_mode=parallel
    action_0001
    action_0002
  step_0002, execution_mode=sequential
    action_0003
```

`parallel` means context-independent actions: sibling actions do not need each
other's outputs. Each action can run from the same base context plus its own
latest-user-message action. The runtime may execute parallel actions as separate
internal agentic sessions, and may do so concurrently when implementation cost is
reasonable. The first implementation may execute them sequentially while
preserving the parallel-capable contract and result shape.

`sequential` means context-dependent actions: later actions may need compact
outputs from earlier actions or steps. The next action receives those compact
outputs when useful, and the current action is appended as the latest user
message.

Each action execution frame should receive:

- base relevant history;
- compact state-specific system context;
- current refs;
- only useful alias, irrelevant-detail, duplicate, and prior-result packets;
- the current action as the final user message.

Each action returns a compact result:

```json
{
  "action_id": "node_action_0001",
  "status": "ok",
  "summary": "node_new_0001 created as Person Lorenzo Tordini.",
  "created_refs": ["node_new_0001"],
  "updated_refs": [],
  "ref_context_delta": {
    "resolved": ["node_new_0001"]
  },
  "diagnostics": []
}
```

The step executor aggregates action results into a compact step result. Later
planning or execution states receive that step result only when it is logically
useful. They do not receive raw child traces.

## Tool Result Behavior

Write and helper tools should return compact, LLM-readable summaries using
local refs. Ref consistency must be preserved across arguments, validation
errors, created/updated refs, diagnostics, child-frame compact results, and
final ingestion summaries.

Example create-node result:

```json
{
  "status": "ok",
  "data": {
    "summary": "node_new_0001 created as Person Lorenzo Tordini.",
    "created_refs": [
      {
        "ref": "node_new_0001",
        "object_kind": "node",
        "label": "Person"
      }
    ],
    "affected_graph_ids": ["node_new_0001"],
    "diagnostics": {
      "backend_id_present": true
    }
  }
}
```

Example validation error:

```json
{
  "status": "recoverable_error",
  "data": {
    "summary": "edge_new_0002 was not created because to_ref 'Marco' is not a known ref.",
    "error_code": "unknown_ref",
    "retryable": true,
    "validation_details": {
      "field": "to_ref",
      "allowed_refs": ["node_0001", "node_0002", "node_new_0001"]
    },
    "suggested_next_action": "Retry with a known node_* ref or ask clarification."
  }
}
```

Tool results may include backend ids in diagnostics, but summaries and
model-facing created/updated refs should prefer `ref`.

## Expected UAT Behavior

For a dense source like the Republic Day barbeque and beach message, the target
output should not be two giant MemoryLogs.

Expected shape:

- many resolved/proposed person refs;
- a few place/event refs;
- several compact MemoryLogs split by coherent episode or observation;
- durable family/partner/perception/context edges only where useful;
- related-target links from memories to involved people and places;
- compact final result explaining refs created/updated.

Example final compact result:

```text
Created node_new_0001 Lorenzo Tordini, node_new_0002 Gianluca Ripari, and
8 additional person/place refs. Created memory_new_0001 through
memory_new_0009 for the barbeque, training, beach, Bang Duel, and evening
episodes. Linked node_new_0001 as the user's brother and node_new_0002 as the
user's cousin. Created context_new_0001 for the perception that the Moon
atmosphere was not great.
```

## Prompt Template Hardening

The final implementation wave should include full prompt-template tuning for the
reasoner, node planner, memory planner, edge planner, and action execution
states.

Production prompts should be code-managed, reviewed, and tested. Prompt templates
should live in Python modules as importable f-string-style string constants or
builder functions, not only as loose markdown files. Runtime-specific values
should be passed through typed placeholders and rendered by small prompt-builder
functions.

Preferred shape:

```python
MEMORY_REASONING_SYSTEM_TEMPLATE = """
# Identity
{identity}

# Context
{context_packet}

# Hard Rules
{hard_rules}

# Guidelines
{guidelines}

# Examples
{shots}

# Output Contract
{output_contract}
"""
```

Each prompt template should contain at least:

- `# Identity`: the state role and responsibility boundary.
- `# Context`: labeled packets such as hydrated graph context, aliases,
  irrelevant details, duplicate candidates, prior step results, and current
  refs.
- `# Hard Rules`: non-negotiable constraints, for example no raw backend ids,
  reasoner does not create refs, edge planner uses refs only, action frames
  execute one action.
- `# Guidelines`: judgement guidance, for example how to split MemoryLogs, when
  to keep weak co-presence as involvement, and how to use aliases.
- `# Examples`: few-shot examples for the state, including dense-memory
  decomposition, duplicate handling, weak-edge no-op, and current-action
  execution.
- `# Output Contract`: the exact structured output schema or tool-use contract
  expected from the state.

Prompt builders should keep stable reusable instructions near the beginning of
the prompt and put request-specific context after the stable rules. Context
packets must remain labeled and compact; do not inject raw object dumps.

State-specific prompt expectations:

- Reasoner prompt: emphasizes high-level guidance, `possible_aliases`,
  `irrelevant_details`, ambiguities, and no ref/action creation.
- Node planner prompt: emphasizes duplicate checks, alias resolution, and
  create/update/no-op planning with refs.
- Memory planner prompt: emphasizes compact MemoryLog boundaries and when to use
  `MemoryLog`, `Claim`, `Perception`, or other context records.
- Edge planner prompt: emphasizes refs-only endpoints, durable edges only, and
  weak co-presence as memory involvement.
- Action execution prompt: emphasizes one current action as the latest user
  message, deterministic write tools, validation-error recovery, and compact
  action results.

The prompt-template wave should include prompt fixtures and tests that render
representative contexts and assert that required sections, placeholders, hard
rules, and examples are present.

## Implementation Waves

Cleanup applies to every wave. Wave 4 is the final hardening pass, but earlier
waves should remove affected legacy code as soon as the replacement behavior is
active and covered.

### Wave 1: Contracts And Ref Context

Goal: introduce the shared LLM ref model without changing ingestion behavior
broadly.

Scope:

- add `RefContext` and `RefEntry` contracts;
- add object-kind and resolution-status enums;
- add backend helpers to allocate readable refs for hydrated graph objects;
- add backend helpers to build minimal LLM-friendly packets for nodes, memories,
  edges, media, and context records;
- add enum-only packet profiles (`short`, `medium`, `long`) while leaving
  contract room for future state-specific overrides;
- add helpers to resolve local refs to backend ids for tools;
- add structured tool-result fields for `ref` summaries and ref-map
  deltas;
- update docs and tests for naming, allocation, child-frame inheritance, and
  compact child-frame ref propagation.

### Wave 2: Structured Reasoning Inventory

Goal: prevent source collapse by forcing ingestion reasoning to separate nodes,
memories, and edges before planning.

Scope:

- add `MemoryIngestionReasoning` contract for structured reasoning guidance;
- keep concrete node, memory, and edge plan ownership in the planning phases;
- add high-level reasoning contracts such as `ReasoningHighlights`,
  `NodeHighlights`, `MemoryLogHighlights`, `EdgeHighlights`, ambiguity notes,
  duplicate/resolution notes, `possible_aliases`, `irrelevant_details`, and
  planning guidance;
- update the `memory_ingestion` prompt to produce mostly free-text reasoning
  guidance separated across nodes, memories, and edges;
- assign refs to hydrated objects before the reasoning call;
- prevent the reasoner from proposing new refs;
- surface duplicate/ambiguity notes for planners to resolve.

### Wave 3: Three-Phase Planning

Goal: replace the single compact plan with specialized planning passes over the
shared reasoning artifact.

Scope:

- add node-planning, memory-planning, and edge-planning prompt templates with
  few-shot examples for splitting dense source text into compact MemoryLogs and
  durable edges;
- add planning contracts for each phase, including step-based plans with
  `parallel` and `sequential` execution modes;
- execute phases in order:
  - node plan and execution;
  - memory plan and execution;
  - edge plan and execution;
- update the ref context after each phase;
- ensure edge planning receives all node and memory refs needed for stable
  linking;
- keep validation errors as tool outputs for the LLM to correct;
- append each current action as the latest user message in action execution
  frames;
- aggregate action outputs into compact step results for later phases.

### Wave 4: Prompt Tuning, UAT Hardening, And Cleanup

Goal: finalize prompt templates, prove dense memories decompose correctly, and
remove older collapsed-plan paths.

Scope:

- move production prompt templates into importable Python f-string-style string
  constants or builder functions with typed placeholders;
- require prompt sections for context, hard rules, guidelines, examples, and
  output contracts;
- add few-shot examples for reasoner, node planner, memory planner, edge
  planner, and action execution states;
- add prompt rendering tests for required sections, placeholders, hard rules,
  and examples;
- add UAT fixtures for dense social/episodic sources;
- assert that long source messages produce multiple compact MemoryLogs and
  useful durable edges;
- assert that edge tools reject natural-language endpoints when a ref is
  required;
- remove or quarantine obsolete single-plan ingestion paths;
- tune prompts to reduce over-creation of weak edges and durable object nodes;
- keep logs readable by showing local refs in summaries and backend ids only in
  diagnostics.

## Non-Goals

- Do not expose raw UUID-heavy context to the LLM as the default.
- Do not require source-span propagation in the core flow for now; selected
  source hints may be used only when useful.
- Do not make every co-occurrence a durable relationship.
- Do not let edge planning invent endpoints outside the ref context.
- Do not rename provisional refs after write.
- Do not reintroduce pending-process or handoff-style deterministic routing.