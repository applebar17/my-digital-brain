# Agentic state framework

## Purpose and status

**Binding framework specification.** An agentic state is a typed, reusable
internal LLM conversation. It receives caller-selected context, carries out one
purpose through the canonical AI client/runtime, and returns its result to the
caller.

This framework is intentionally small. It does not define a fixed orchestrator,
pipeline language, dependency-injection system, status model, or domain
workflow. Specific ingestion, retrieval, clarification, and chat behavior is
configured by the states that need it.

The framework builds on the imported `ai_clients` design as its client-facing
foundation, but it does not authorize use of the copied reference package in
the active application. Its typed replacement remains governed by the
[client-runtime rebuild plan](../migration/client-runtime-rebuild-plan.md).

## Responsibility boundary

An agentic state composes an LLM client; it does not inherit from the client.

| Component | Owns | Does not own |
| --- | --- | --- |
| `LLMInterfaceCore` / canonical replacement | provider request translation, provider transcript, tool-call loop, and provider-call ID pairing | domain-specific prompt construction or agent purpose |
| `BaseAgenticState` | local invocation context, one request appended to local history, client request assembly, and state result normalization | provider-specific tool-message protocol or a second tool loop |
| Concrete state | recurring system-prompt, toolbox, request, and output choices for one purpose | unrelated orchestration or provider configuration |
| Invoker | chooses direct invocation or tool registration, supplies appropriate history/context, and consumes the result | child state internals |

This separation preserves the dependency direction defined by
[dependency-oriented module design](../../requirements/technical/dependency-oriented-module-design.md):
contracts first, then runtime capabilities, then concrete states and their
composition.

## Building blocks

Exact Python module paths and final DTO field names are implementation work.
The following is the required semantic contract; feature code must not create
alternative shapes for the same concepts.

### `AgenticStateInvocationDTO`

Each call supplies one typed invocation object containing only the context
needed for that internal conversation:

- **System prompt**: caller-built text. The base state does not compose prompt
  templates or infer missing instructions.
- **Internal conversation history**: the selected master or local history
  supplied by the invoker. The state creates a local working transcript and
  does not mutate the caller's history object.
- **Invocation request**: the externally configured purpose, user message, or
  agentic request. It is appended once as the final `user` request in the
  state-local history.
- **Optional structured-output request**: the typed final artifact expected
  from this state, when its caller needs one.
- **Toolbox**: the typed map of available tool definitions and executables for
  this invocation.

The LLM client itself, logging, provider route, and other executable resources
are runtime dependencies of the state, not conversation-history payloads.

### `BaseAgenticState`

The base class has one primary typed entrypoint, conceptually:

```python
invoke(invocation: AgenticStateInvocationDTO) -> AgenticStateResultDTO
```

Its sequential responsibility is:

1. structurally validate the invocation DTO;
2. create the state-local transcript from its system prompt and supplied
   history;
3. append the invocation request as one user message;
4. ask the client to normalize the request, including the supplied toolbox and
   optional structured-output request;
5. invoke the client session through its `call(...)` entrypoint;
6. map the canonical session outcome to an `AgenticStateResultDTO` for the
   invoker.

The base state never manually appends provider tool messages, allocates tool
call IDs, invokes a second tool loop, invents an assistant completion, or turns
a tool result into a user-facing final message. Those responsibilities remain
in the client/runtime described by the
[tool-calling protocol](tool-calling-protocol.md).

### `AgenticStateResultDTO`

The result conveys the state outcome to its caller, rather than exposing raw
provider objects or an internal transcript. It carries the terminal assistant
result and, when requested, the validated structured artifact. It also carries
the existing runtime outcome when the session is awaiting user input or has
failed.

The exact response fields must reuse the canonical session and structured-output
contracts; do not add diagnostic blobs, transport IDs, invented processing
statuses, or duplicate result fields without an accepted consumer need.

## Toolbox lifecycle

Toolboxes are configured per invocation, but their executable entries will
normally come from one application-level toolbox of partially initialized
functions and agent states. That shared toolbox is assembled at an explicit
composition boundary.

A concrete state may supply a different or augmented toolbox when its accepted
purpose requires another agent or a specific initialized object. This remains
an explicit configuration decision of that state/invocation; it is not a reason
to introduce a general service locator, mutable global registry, or automatic
tool discovery.

Every toolbox entry follows the canonical typed `ToolDefinition` and handler
contract in [DTO-first contracts](../contracts/dto-first-contracts.md). An
agentic state can therefore appear alongside ordinary functions in the same
toolbox.

## Direct invocation and agent-to-agent invocation

The state entrypoint is the same in both modes:

```text
direct: caller -> state.invoke(invocation) -> state result
as a tool: parent tool handler -> child_state.invoke(invocation) -> parent tool output
```

There is no separate agent-to-agent conversation protocol. When a state is
registered as a tool, its handler translates the validated parent tool input
into an `AgenticStateInvocationDTO`, invokes the child, and returns one compact
typed output for the parent tool call.

The parent and child have independent local transcripts. The child may call its
own tools, including other states. The runtime pairs all child calls within the
child transcript; only the parent tool's original provider call ID is used when
the compact child result is returned to the parent. This is the nested-agent
rule in the [tool-calling protocol](tool-calling-protocol.md#nested-agent-tools).

Do not create an additional `AgenticStateTool` class hierarchy unless a concrete
accepted use case proves that a simple typed tool handler cannot express the
binding above.

## Concrete state inheritance

A concrete state inherits `BaseAgenticState` only to reuse its stable invocation
lifecycle. It may provide a purpose-specific public method that builds the
accepted invocation configuration—such as a recurring system prompt, toolbox,
request format, or structured-output request—and delegates once to
`BaseAgenticState.invoke(...)`.

The base class must not gain optional hooks for hypothetical state types. Add an
extension point only after at least one accepted concrete state needs it and the
shared behavior is explicit. Prefer passing a prepared invocation DTO over
making a base class guess caller intent.

Important `invoke` methods and purpose-specific configuration methods follow
the contextual method-documentation rule: state their purpose, immediate
collaborators (for example, prompt builder, toolbox, or client), contract, and
material side effects.

## Structured output and terminal outcomes

Structured output is a request for the state’s final artifact, not a fake
submission tool. The client/provider contract parses and validates it according
to [DTO-first contracts](../contracts/dto-first-contracts.md#structured-model-outputs).

The state preserves the runtime outcomes already defined by the canonical
protocol:

- `completed`: final assistant result, optionally with its validated structured
  artifact;
- `awaiting_input`: an existing pausing tool requires the caller/UI to collect
  user input before the same local transcript resumes;
- `failed`: an unrecoverable runtime/provider problem for the invoking layer to
  render safely.

Tool success and failure remain model-transcript events, not state final chat
messages. A child state result becomes visible to a parent model only through
the parent’s matched tool output.

## Implementation order

Document and test the framework before migrating application agents:

1. establish canonical session, tool, and structured-output DTOs;
2. establish the generic client runtime and typed toolbox registration;
3. implement the base invocation/result DTOs and `BaseAgenticState`;
4. migrate one accepted concrete state at a time, deleting its superseded
   invocation path immediately after its final caller moves.

No state migration may retain a second client loop, untyped tool mapping, or
legacy conversation path in parallel with the canonical one.
