# Tool-calling protocol

## Non-negotiable invariant

One provider-issued tool call receives exactly one matching tool output. Tool
calls and tool outputs remain inside the model transcript; neither is a final
chat API message.

The required owner of this loop is `LLMInterfaceCore` in
[`ai_clients`](../../../src/my_digital_brain/ai/ai_clients/README.md), using its
provider adapters. Agentic states configure the toolbox and call the client;
they do not parse provider tool-call objects, run a second loop, or synthesize
tool-call IDs. See the [agentic-state framework](agentic-state-framework.md)
for the state/client boundary.

The OpenAI Responses API represents a function result as a
`function_call_output` that refers to the original function `call_id`.
The provider adapter normalizes this into the application-wide
`provider_call_id` contract. [Official OpenAI function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling)
describes the same call-to-output correlation.

## Normal path

```text
provider completion
  -> assistant turn, with zero or more provider tool calls
  -> persist assistant turn unchanged in the session transcript
  -> normalize each call to ToolCallDTO
  -> validate + execute each mapped tool
  -> append exactly one matching tool output per provider_call_id
  -> provider completion with the updated transcript
  -> final assistant text only when the assistant returns no tool calls
```

The runtime, not a prompt, guarantees the return to the provider after a tool
output. A model is never asked to "continue" through ordinary prose.

## Failure path

```text
assistant tool call
  -> DTO/domain/handler failure
  -> one ToolOutputDTO(status=error or recoverable_error)
  -> matching provider tool-output message
  -> next provider completion
  -> assistant response or a further tool call
```

A failure must not skip the matching output, emit a second output for the same
call, terminate the outer session, or leak its serialized output to chat as the
final answer.

## Pending human interaction

Clarification is a pausing tool, not an alternative response protocol.

```text
assistant calls request_clarification
  -> persist the open assistant tool call and paused frame
  -> return a UI interaction packet, without a tool output yet
user submits answer
  -> validate answer deterministically
  -> append exactly one output for the original provider_call_id
  -> resume the same state-local transcript
```

## Nested agent tools

An agent may be registered as a tool. This creates two independent transcripts:

```text
parent assistant call (parent_call_id)
  -> child-tool handler starts child session
  -> child session may execute its own calls and use child_call_ids
  -> child completes or pauses
  -> handler compacts child result into one parent ToolOutputDTO
  -> parent transcript receives one output for parent_call_id
```

Child call IDs never replace, duplicate, or escape into the parent transcript.
Only the parent tool's original `provider_call_id` pairs with the parent output.

## Tool-call cap and final response

The client applies a configurable maximum number of tool calls, with a default
defined by client configuration. Reaching this cap is not a terminal outcome
and must not end the state or caller interaction.

When the cap prevents execution of provider-requested calls, the client keeps
the provider's assistant tool-call turn and appends one fabricated tool output
for each outstanding call that it cannot execute. Each output uses that
call's original `provider_call_id` and explains that the call was not executed
because the configured tool-call cap was reached. The client does not invent
provider tool calls or provider call IDs. This preserves the one-call/one-output
transcript contract while giving the model the reason the requested work did
not run.

The client then makes a final provider request with the toolbox removed. The
provider must produce the assistant response; the client does not fabricate an
assistant completion. The returned response follows the normal state-to-caller
path, including when this state was itself invoked as a tool by another agent.

```text
provider assistant tool calls
  -> execute calls while under the configured cap
  -> for any calls declined at the cap, append matching synthetic tool outputs
  -> next provider request has no toolbox
  -> return the provider's assistant response to the invoker
```

The cap limits tool execution, not completion of the conversation. It is a
continuation path, not a `failed` or `awaiting_input` outcome.

## Terminal states

A logical session may return only one of these outcomes:

- `completed`: a provider assistant turn with no tool calls; it may contain
  final text or a validated structured output.
- `awaiting_input`: one or more open pausing tool calls, with a persisted frame.
- `failed`: only after an unrecoverable runtime/provider failure. Its API layer
  creates a user-safe error response; it does not present a tool payload as text.

The configured tool-call cap is handled by the continuation path above. It is
not a terminal/runtime outcome. Only an explicitly approved pipeline-breaking
condition may intentionally stop the interaction before a provider assistant
response is returned.

## Required runtime tests

- one call -> one output -> next provider turn -> final text;
- handler exception -> one error output -> next provider turn;
- two calls in one assistant turn -> two independently matched outputs;
- calls declined at the configured cap -> one synthetic output per original
  call ID, then a provider turn with no tools and an assistant response;
- duplicate `provider_call_id` is rejected before execution;
- an inner agent tool produces exactly one outer output;
- clarification pauses with no premature output and resumes with one output;
- no serialized tool output can become a `completed.content` value.
