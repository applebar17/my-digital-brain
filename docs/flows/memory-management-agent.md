# Memory Management Agent

## Purpose

The memory management agent is a future toolbox for maintaining the digital brain without forcing the user into mechanical admin flows.

It should act through simple chat interactions and safe tools.

## Responsibilities

- Detect contradictions.
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

When a new memory conflicts with existing memory, the agent should decide whether it is:

- A real contradiction.
- A temporal update.
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

Contradiction notifications should be sent through the active chat interface when the contradiction matters. They should be phrased as a simple clarification, not as a system error.

Do not notify when:

- The contradiction is low confidence.
- The facts may both be true at different times.
- The difference is not useful enough to interrupt the user.
- The system can safely preserve both as uncertain memories.

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
