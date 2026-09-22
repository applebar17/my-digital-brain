# Reference `ai_clients` assessment

## Status

`src/my_digital_brain/ai/ai_clients/` is an imported reference package on the
clean-slate migration branch. The active application does not import it. Its
copied `boris.boriscore` imports have been replaced with project-local imports,
but it still depends on provider/runtime packages that are not declared as
application dependencies.

It is useful design evidence and a migration source, not production code yet.

## Valuable behavior to preserve

`llm_core/llm_core.py:handle_tool_calling` demonstrates the correct essential
sequence:

1. Keep the assistant tool-call turn in the transcript.
2. Resolve the requested tool through a backend mapping.
3. Parse the tool arguments into a typed input object.
4. Execute the mapped tool.
5. Serialize its success or failure as a tool message paired to the original
   provider-issued call identifier.
6. Call the provider again with the expanded transcript.

It also shows useful concerns that belong in the target runtime: bounded tool
rounds, repeat-call protection, compact model-facing tool outputs, and a
per-call trace record.

## Gaps that must not be carried forward

| Reference behavior | Why it is unsuitable as the target | Target rule |
| --- | --- | --- |
| Copied package namespace and undeclared optional dependencies | Import normalization alone does not establish a supported application module. | Keep it isolated, declare or remove each dependency deliberately, and port reviewed pieces under `my_digital_brain.ai`. |
| Dataclass and dictionary fallback parsing | It permits ambiguous handler input and hides contract drift. | Pydantic input/output DTOs; parse once at the runtime boundary. |
| `partial` mapping and `fn(**parsed_kwargs)` | Tool signatures are not self-documenting or consistently typed. | Typed `ToolDefinition` plus `handler(context, input_dto)`. |
| `tc.id` used directly | Identifier semantics differ by provider endpoint. | Adapter normalizes the provider ID into `provider_call_id`. |
| Tool-specific behavior in generic core (`retrieve_node`) | The core becomes coupled to one domain and cannot be reused. | Generic runtime only; domain retries and policy belong to tools/services. |
| Mutation of request objects and recursive re-entry | It makes session ownership and terminal state difficult to inspect. | Iterative session runner with immutable/append-only transcript semantics. |
| Synthetic assistant messages when tooling is disabled | It can imply completion without a provider-produced final response. | Runtime returns an explicit limit/failure result or performs a final provider turn with tools disabled. |

## Current active-runtime comparison

The active stack is `ai/client`, `ai/providers`, and `ai/session`. It already
has pieces of the desired behavior: a provider-neutral `LLMSessionRunner`, a
`ToolExecutor`, Pydantic session DTOs, stored continuations, and result-message
canonicalization. Its failures indicate that ownership and contracts have
drifted across the larger agentic layer, not that the basic loop should be
replaced by copied code.

The migration should therefore establish the DTO registry and transcript
invariants first, migrate provider adapters and tool dispatch second, then
delete the obsolete runtime paths. It must not run both client frameworks in
parallel indefinitely.
