# Tool definition and toolbox contracts

## Decision

A tool is defined once as a typed application capability. From that definition
the provider adapter compiles the exact provider-facing JSON-like declaration,
validates model arguments into an input DTO, and invokes one bound backend
handler. The handler returns its typed domain output; the client wraps that
output in one provider-facing `ToolOutputDTO` matched to the original call.

The provider declaration is an adapter output, not the source of truth. Tool
names, descriptions, input-field descriptions, and enum meanings stay in the
typed definition. Successful output semantics stay explicit in the handler's
annotated return DTO for implementation and debugging.

## Tool layers

```text
Input DTO field annotations + descriptions
  -> ToolDefinitionDTO
  -> RegisteredTool (definition + typed handler)
  -> ToolBox (named registrations)
  -> provider adapter emits OpenAI-compatible function declaration
  -> provider ToolCallDTO
  -> validated Input DTO -> handler -> domain OutputDTO
  -> ToolOutputDTO(status="ok") or ToolOutputDTO(status="error")
```

`ToolDefinitionDTO` is the model-facing declaration. `RegisteredTool` pairs it
with the typed executable. Keeping those roles distinct means no provider JSON
dictionary, global string handler key, or untyped `**kwargs` is treated as the
application contract.

## Typed definitions

The final field names may vary only if they preserve these responsibilities:

```python
class ToolDefinitionDTO(BaseModel):
    """Model-facing semantic definition of one callable capability."""

    name: str
    description: str
    input_model: type[BaseModel]


class RegisteredTool[InputDTO: BaseModel, OutputDTO: BaseModel]:
    """One definition paired with its typed backend implementation."""

    definition: ToolDefinitionDTO
    handler: Callable[[InputDTO], OutputDTO]


class ToolBox:
    """Named set of registered tools for one state purpose."""

    name: str
    tools_by_name: Mapping[str, RegisteredTool]
```

`InputDTO` field annotations and `Field(description=...)` values are the
semantic schema. They explain every model-visible parameter: purpose, valid
form, units or enum meaning where relevant, and the boundary between similar
fields. The generated JSON Schema must retain those descriptions. They are
therefore inspectable in tool diagnostics without reverse-engineering raw
provider payloads.

`OutputDTO` is the tool-specific successful domain result and is explicit in
the handler's return annotation. It is not repeated as an `output_model` field
in `ToolDefinitionDTO`. The client wraps successful data in
`ToolOutputDTO(status="ok")`; invalid arguments or handler failures become
`ToolOutputDTO(status="error", error=ToolErrorDTO(...))`. These are the only
tool-output statuses. Human-input pauses belong to state/session flow and do
not create a pending tool result.

## OpenAI function declaration adapter

The OpenAI adapter compiles `ToolDefinitionDTO` and its `input_model` into the
base function shape accepted by the selected API. The semantic content is the
same in both forms:

```json
{
  "type": "function",
  "name": "query_memory",
  "description": "Retrieve grounded memory context for a user question.",
  "parameters": {
    "type": "object",
    "properties": {
      "question": {
        "type": "string",
        "description": "The user's memory question to investigate."
      }
    },
    "required": ["question"],
    "additionalProperties": false
  },
  "strict": true
}
```

For the **Responses API**, that object is one item in `tools` exactly as shown.
For **Chat Completions**, the provider adapter emits the compatibility wrapper:

```json
{
  "type": "function",
  "function": {
    "name": "query_memory",
    "description": "Retrieve grounded memory context for a user question.",
    "parameters": { "...": "same JSON Schema" },
    "strict": true
  }
}
```

The active provider baseline will select the relevant adapter; agentic states,
tool registrations, and domain handlers never branch on this provider shape.

`strict` is an explicit adapter capability choice, never an accidental
default. When enabled, the schema compiler must emit an OpenAI strict-compatible
schema: every object declares `additionalProperties: false`, every property is
listed in `required`, and semantically optional fields are nullable. If an
accepted input DTO cannot be represented in the chosen strict profile, the
adapter reports a developer-facing configuration diagnostic before sending the
request. It does not add application validation policies or alter tool
semantics to make a schema fit.

This matches the official OpenAI function-tool contract: `type`, `name`,
`description`, `parameters`, and `strict`; `parameters` is JSON Schema and
strict mode has the additional-object and required-property constraints.
[Official OpenAI function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling)
defines this provider surface.

## Registration and composition

Tools are assembled at an explicit application composition boundary, where
their dependencies are available. A graph tool binds a graph service; a vector
tool binds a retrieval service; an agentic tool binds a concrete child state.
The resulting toolboxes are stable purpose-specific values, for example:

```text
conversation_entry_toolbox
memory_query_toolbox
memory_creation_toolbox
```

A state receives the toolbox it is configured to use. The runtime dispatches a
provider call by tool name within that supplied toolbox. It does not consult a
global mutable registry, dynamically discover tools, or map a second string
such as `handler_key` to an executable.

An agentic child state needs no special framework type. Its registered handler
validates the parent input DTO, prepares the child invocation, calls
`child_state.invoke(...)`, then maps the completed child result to its typed
domain output. The client wraps that output once for the original parent call.
If the child pauses for human input, the state/session pauses and resumes the
same invocation; no pending tool-output status is introduced. The nested-call
identity rule remains owned by the
[tool-calling protocol](../runtime/tool-calling-protocol.md#nested-agent-tools).

## Invocation and diagnostics

The runtime parses `ToolCallDTO.arguments_json` once through the registered
input model and calls the handler with that validated DTO. Dependencies are
bound when the toolbox is composed; a generic execution-context object is not
added unless a concrete per-invocation need is identified. The handler's
annotated return type defines its successful output. The client serializes
exactly one `ToolOutputDTO` against the immutable provider call ID.

Tool diagnostics show both the semantic descriptor and the compiled provider
declaration:

- tool name and concise capability description;
- input DTO name, fields, annotations, descriptions, enum values, and required
  versus nullable semantics;
- handler return DTO name and fields, from its return annotation;
- selected provider adapter and emitted function declaration;
- the provider call ID, validated arguments, and typed outcome.

The diagnostic surface is for development and traceability. It must not become
a generic user-facing chat payload or add opaque status fields to domain
results.

## Migration rules

The existing `ToolSpec` dictionaries, `AgenticToolRegistry`, `allowed_tools`,
and string `handler_key` dispatch are migration material. The replacement is
completed toolbox by toolbox:

1. define the input DTO and its field descriptions;
2. define the successful output DTO and annotate the handler return type;
3. create one tool definition and its typed handler;
4. assemble the state-specific `ToolBox` at the composition boundary;
5. compile it through the provider adapter and add contract fixtures;
6. move the state caller, then delete the superseded declaration and dispatch
   path in that same wave.

No duplicated registry or compatibility mapping remains after a toolbox has
migrated.

## Verification

Each registered tool has tests for input DTO schema semantics, the Responses
and Chat Completions emitted shapes where those adapters are supported, valid
argument parsing, invalid-input error output, handler failure output, and exact
provider-call-ID pairing. Each toolbox has a duplicate-name construction test
and a fixture showing the complete model-visible declaration set.
