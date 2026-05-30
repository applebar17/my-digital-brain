# Memory Management Agent

## Purpose

The memory management agent is a future toolbox for maintaining the digital brain without forcing the user into mechanical admin flows.

It should act through simple chat interactions and safe tools.

## Responsibilities

- Review contradiction suspicions raised by memory-writing agents.
- Ask clarification when contradictions matter.
- Propose merges and splits.
- Mark facts as stale, expired, disputed, or confirmed.
- Update contact details.
- Attach or detach evidence.
- Promote metadata into structured fields.
- Explain why a memory exists.

## Non-Goals

- Do not turn every ingestion into a review task.
- Do not require the user to manage graph internals.
- Do not aggressively prune memories, because preservation is the core purpose.
- Do not make irreversible changes without explicit confirmation.

## Contradiction Handling

Contradiction handling should start from agentic suspicion, not deterministic contradiction rules.

During ingestion, the memory-writing agent receives focused graph context before writing. If it sees a possible conflict, it invokes a contradiction judge tool with:

- proposed write
- retrieved graph context
- affected entities and relationships
- source references
- short explanation of the doubt

The contradiction judge can then inspect more graph context through read-only tools.

When a new memory appears to conflict with existing memory, the judge should decide whether it is:

- A real contradiction.
- A temporal update.
- A relationship state change.
- A nuance that can be stored without conflict.
- A different entity with a similar name.
- A low-confidence extraction issue.
- Not important enough to interrupt the user.

If clarification is useful, the chatbot can ask:

```text
I found a possible conflict: I had Luca's phone number as X, but you just mentioned Y. Should I mark Y as the current number?
```

```text
You previously said this happened in Rome, but this message says Milan. Were these two different events?
```

Contradiction notifications should be sent through the active chat interface when the judge decides the contradiction matters. They should be phrased as a simple clarification, not as a system error.

Do not notify when:

- The judge classifies the issue as low severity.
- The facts may both be true at different times.
- The difference is not useful enough to interrupt the user.
- The system can safely preserve both as uncertain memories.

## Contradiction Judge Output

The judge should return structured output:

- `decision`: no_conflict, nuance, temporal_update, contradiction, needs_clarification.
- `severity`: low, medium, high.
- `reason`
- `graph_action`: allow_write, write_as_disputed, create_contradiction_record, create_relationship_state, ask_user.
- `clarification_question`

The judge should not mutate the graph directly. It recommends actions that the AI Manager or Network API executes through approved tools.

Deterministic guardrails still apply:

- max read/tool iterations
- read-only graph access during investigation
- structured output validation
- privacy checks
- persistence of judge decisions when they affect memory

## Clarification Style

The system should avoid mechanical review queues at first. It should retain the user through natural conversation:

- Ask one focused question at a time.
- Ask when the answer improves memory quality.
- Prefer inline options for common cases.
- Allow the user to skip.
- Store low-precision or uncertain facts when interruption is not worth it.

## Tool Contract

Future tools should be explicit and auditable:

- `confirm_fact`
- `dispute_fact`
- `expire_fact`
- `archive_memory`
- `delete_memory`
- `merge_entities`
- `split_entity`
- `update_contact_point`
- `attach_evidence`
- `promote_metadata`
- `ask_clarification`

Each tool call should record actor, reason, evidence, timestamp, and reversibility.

## User Experience

The user should experience the agent as a helpful memory assistant:

- "I noticed a possible duplicate."
- "This looks like an updated address."
- "I can keep both memories, but mark one as older."
- "I am not sure whether this is the same Giulia."

The goal is better memory, not database maintenance.
