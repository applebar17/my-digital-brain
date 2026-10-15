# Required `ai_clients` target layer

## Status

`src/my_digital_brain/ai/ai_clients/` is the required target client layer for
the rebuilt agentic framework. It is not currently imported by the active
application, and its provider/runtime dependencies still need an explicit
production dependency decision. The package is the selected foundation; it is
not a disposable example or merely one candidate among client implementations.

The package may receive focused changes where its current implementation
conflicts with the canonical DTO, provider-adapter, or tool-calling contracts.
The contracts in `docs/ai-engineering/` are the design source of truth; current
package and application code are inspected to locate concrete discrepancies
and integration seams. Do not create a competing provider client or tool loop.
This is a target-boundary note, not an implementation plan. The file census is
owned by [Wave 0](../../plans/agentic-framework-rebuild/wave-0-census/README.md).

## Valuable behavior to preserve

`llm_core/llm_core.py` is the designated location for client-level request
parameter handling and the shared provider/tool-call lifecycle. The required
sequence is specified by the canonical
[tool-calling protocol](../runtime/tool-calling-protocol.md):

1. Keep the assistant tool-call turn in the transcript.
2. Resolve the requested tool through a backend mapping.
3. Parse the tool arguments into a typed input object.
4. Execute the mapped tool.
5. Serialize its success or failure as a tool message paired to the original
   provider-issued call identifier.
6. Let the client call the provider again with the expanded transcript.

`LLMInterfaceCore.call(...)` is the entrypoint used by an agentic state. The
client owns provider invocation through an adapter and the iterative tool
loop. The state owns its purpose, prompt/context, typed toolbox configuration,
and interpretation of the terminal client result. A nested state is exposed to
the client as an ordinary mapped tool executable and returns one typed output
to its invoking loop.

The package is reviewed against documented requirements such as a configurable
tool-call cap with a non-breaking final provider turn, typed argument/result
handling, one output per provider call ID, and actionable failure output.
Existing implementation details are not approved solely because they are
present in the package.

## Gaps that must not be carried forward

| Reference behavior | Why it is unsuitable as the target | Target rule |
| --- | --- | --- |
| Copied package namespace and undeclared optional dependencies | Import normalization alone does not establish a supported application module. | Keep the selected package; declare or remove each dependency deliberately before production integration. |
| Dataclass and dictionary fallback parsing | It permits ambiguous handler input and hides contract drift. | Pydantic input/output DTOs; parse once at the runtime boundary. |
| `partial` mapping and `fn(**parsed_kwargs)` | Tool signatures are not self-documenting or consistently typed. | Typed `ToolDefinition` plus `handler(context, input_dto)`. |
| Provider-native IDs handled outside the adapter boundary | The provider-specific field name/shape belongs to each adapter. | Preserve the original provider ID and normalize it once to `provider_call_id` for all upper layers. |
| Tool-specific behavior in generic core (`retrieve_node`) | The core becomes coupled to one domain and cannot be reused. | Generic runtime only; domain retries and policy belong to tools/services. |
| Mutation of request objects and recursive re-entry | It makes session ownership and terminal state difficult to inspect. | Iterative session runner with immutable/append-only transcript semantics. |
| Tool-cap handling that terminates the state or fabricates assistant completion | It can leave the invoker without a final assistant response or falsely imply completion. | For provider calls declined at the configured cap, append synthetic tool outputs matched to their original call IDs, remove tools from the next request, and return the provider-produced assistant response. Never fabricate provider call IDs or assistant completion messages. |

## Current active-runtime comparison

The active stack currently includes `ai/client`, `ai/providers`, and
`ai/session`. Wave 0 records their callers, DTO dependencies, and any
application capabilities that need to remain available. It does not choose
that stack over the required `ai_clients` target. Any useful behavior or
integration constraint is captured as evidence and reconciled against the
canonical contracts before implementation planning.
