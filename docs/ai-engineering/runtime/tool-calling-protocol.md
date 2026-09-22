# Tool-calling protocol

## Non-negotiable invariant

One provider-issued tool call receives exactly one matching tool output. Tool
calls and tool outputs remain inside the model transcript; neither is a final
chat API message.

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

## Terminal states

A logical session may return only one of these outcomes:

- `completed`: a provider assistant turn with no tool calls; it may contain
  final text or a validated structured output.
- `awaiting_input`: one or more open pausing tool calls, with a persisted frame.
- `failed`: only after an unrecoverable runtime/provider failure. Its API layer
  creates a user-safe error response; it does not present a tool payload as text.

Tool-loop limits protect resources, but reaching a limit is handled as an
explicit terminal/runtime outcome with trace context. The runtime must not
invent an assistant message saying that work is complete.

## Required runtime tests

- one call -> one output -> next provider turn -> final text;
- handler exception -> one error output -> next provider turn;
- two calls in one assistant turn -> two independently matched outputs;
- duplicate `provider_call_id` is rejected before execution;
- an inner agent tool produces exactly one outer output;
- clarification pauses with no premature output and resumes with one output;
- no serialized tool output can become a `completed.content` value.
