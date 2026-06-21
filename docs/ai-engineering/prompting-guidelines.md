# Prompting Guidelines

## Purpose

System prompts should provide the minimum stable guidance needed for the model to do the current job well. They are not documentation for the backend, not a place to restate orchestration mechanics, and not a dump of every rule the system already enforces elsewhere.

The guiding principle is: fewer words, clearer behavior, lower cost.

## Core Rules

### 1. Remove Everything The Model Does Not Need

Every sentence in a system prompt must help the model decide what to do with the context, tools, messages, and output contract it can actually see.

Bad:

```text
You are the reusable planning checkpoint and ingestion planner for a network graph flow in My Digital Brain.
```

Better:

```text
You're a planner.
```

If a product name, backend subsystem, lifecycle detail, or implementation label does not change model behavior, remove it.

### 2. State The Process Scope Directly

The prompt must say what this specific LLM process is responsible for. Scope beats identity verbosity.

Example:

```text
Plan node creation for a memory graph. Return the ordered node actions needed before memory logs and edges are planned.
```

A good scope line answers:

- What is the model doing?
- What object or phase is it working on?
- What should its output be used for?

### 3. Define Domain Terms Only When They Drive Decisions

Definitions are useful when they prevent bad plans. Keep them short and pair them with examples.

Example:

```text
A node is a self-sustaining graph entity: a person, place, event, or social circle. Do not create nodes for incidental details that only make sense inside one memory log.
```

Useful definitions explain boundaries:

- Node versus MemoryLog.
- Durable edge versus weak co-presence.
- Perception or relationship context versus ordinary event detail.
- Alias versus duplicate person.

Avoid definitions that explain backend internals or storage mechanics the model cannot act on.

### 4. Rules Must Be Behavioral, Not Backend Reassurance

Rules should guide model judgment. Do not include rules for constraints already guaranteed by the caller, schema, tool availability, or backend validation unless the rule changes model behavior.

Usually unnecessary:

```text
Execute exactly one current MemoryPlanAction.
```

If the current action is already appended as the latest user message and the tool loop only gives the model that action, this rule is noise.

Better:

```text
Use the current action as the task. If a tool rejects your arguments, fix the arguments and retry when the correction is clear.
```

Good behavioral rules:

- Split dense episodic memories into compact logs.
- Resolve aliases before proposing new person nodes.
- Create durable edges only for explicit relationship evidence.
- Keep weak co-presence as MemoryLog involvement.
- Ask clarification only when the missing fact blocks the action.

Bad rules:

- Backend will validate fields.
- Do not mutate the database if no write tool is available.
- Use deterministic services.
- Return JSON because the schema already enforces JSON.

### 5. Prompt For The Context The Model Actually Receives

The model reasons over the visible prompt, messages, tool descriptions, schemas, and context packets. System prompts should reference those surfaces, not hidden backend state.

Good:

```text
Use the provided ref packet. Edge endpoints must use refs from that packet.
```

Bad:

```text
Do not invent backend UUIDs.
```

If backend IDs are not shown to the model, this mostly teaches the model irrelevant vocabulary. Prefer model-facing terms like `refs`, `packets`, `current action`, `known aliases`, and `candidate nodes`.

### 6. Keep Stable Instructions Early, Dynamic Packets Late

Put compact stable behavior first. Request-specific context should be injected in clearly labeled packets after the stable rules.

Recommended order:

```text
# Role
You're a planner.

# Task
Plan node creation for a memory graph.

# Definitions
...

# Rules
...

# Examples
...

# Context
Known refs:
{ref_context_packet}

Reasoning notes:
{reasoning_inventory_packet}
```

The exact section names can vary, but the principle should not: durable instructions first, dynamic context clearly labeled later.

### 7. Use Shots For Ambiguous Boundaries

Examples are more valuable than long abstract rules. Use few shots when the model must distinguish similar cases.

Example for edge planning:

```text
"Lorenzo is my brother" -> durable family edge.
"Lorenzo was at the beach too" -> MemoryLog involvement only.
```

Example for node planning:

```text
"Merc" with candidate "Matteo Mercoldi" -> resolve alias before creating a new person.
"a blue towel" mentioned once -> do not create a node unless it matters later.
```

Shots should be short, realistic, and targeted to common failure modes.

### 8. Prefer Context Engineering Over Prompt Bulk

If the model needs better behavior, first improve the packets, tool descriptions, schema descriptions, or message ordering. Do not expand the system prompt by default.

Ask before adding prompt text:

- Can this be handled by a cleaner packet?
- Can this be handled by a schema field description?
- Can this be handled by a shot instead of a paragraph?
- Can this be handled by backend validation/tool feedback?
- Is this instruction already implied by available tools or output schema?

### 9. Optimize For The 99 Percent Case

A system prompt should cover normal behavior and common edge cases. Rare exceptions should usually be handled by tool errors, validation feedback, or clarification loops.

The prompt should not try to describe every backend branch. Over-specified prompts cost more, distract the model, and make future behavior harder to reason about.

## Prompt Review Checklist

Before accepting a prompt, check:

- Can the first sentence be shorter without losing behavior?
- Is the exact process scope clear?
- Are domain definitions short and decision-relevant?
- Are rules behavioral rather than backend-explanatory?
- Are hidden backend concepts removed?
- Are dynamic context packets clearly labeled?
- Are examples covering the main ambiguity boundaries?
- Is any instruction duplicated by the schema, tool surface, or caller setup?
- Would a model produce the same output if this sentence were removed? If yes, remove it.
