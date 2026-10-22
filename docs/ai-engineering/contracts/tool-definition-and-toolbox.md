# Tool definition and toolbox contracts

## Decision

A tool is defined once as a typed application capability. From that definition
the provider adapter compiles the exact provider-facing JSON-like declaration,
validates model arguments into an input DTO, and invokes one bound backend
handler. The handler returns its typed domain output; the client wraps that
output in one provider-facing `ToolOutputDTO` matched to the original call.

The provider declaration is a client-boundary output, not the source of truth.
Tool names, descriptions, input-field descriptions, and enum meanings stay in
the typed definition. Successful output semantics stay explicit in the
handler's annotated return DTO for implementation and debugging.

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

The unique framework DTO is owned by
`product.ai.ai_clients.protocols.protocol_tools`. Generic typed registrations
and the state-specific `ToolBox` are owned by `product.agentic.tools`. A toolbox
derives both its client definitions and callable mapping from the same
registrations; the state passes those to the client request and call
respectively. The client compiles the DTO into its canonical tool
representation, and each provider adapter translates that representation for
its API.

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

## Typed graph-action tool pattern

Product graph writes use a small operation surface rather than one provider
function for every node subtype. A single registered graph-action function is
bound to one dispatcher; its input is a typed union of concrete action DTOs.
Each variant fixes its `operation`, `kind`, and `type` and declares only the
fields that operation/type accepts. For example, a Person-create variant and
a Place-create variant share the action identity, but keep person and place
properties in their own annotated DTOs.

```python
from typing import Literal


class GraphActionBase(BaseModel):
    """Fields genuinely shared by concrete graph actions."""

    ref: str  # model-local ref; never a backend UUID


class CreatePersonActionDTO(GraphActionBase):
    operation: Literal["create"]
    kind: Literal["node"]
    type: Literal["PERSON"]
    person: PersonCreateFieldsDTO


class CreatePlaceActionDTO(GraphActionBase):
    operation: Literal["create"]
    kind: Literal["node"]
    type: Literal["PLACE"]
    place: PlaceCreateFieldsDTO
```

The model-facing tool has an object root containing an `action` union. The
toolbox composer builds that union only from predeclared action DTO variants
allowed for the current state and, when applicable, narrowed by its validated
plan. The plan may select among supported capabilities; it cannot add a type,
field, operation, or handler. Concrete variants map to the same registered
graph-action dispatcher, which routes the validated DTO to the owning typed
deterministic service. This keeps the provider tool count small without
replacing field-level contracts with a generic `properties` or `metadata`
dictionary.

`operation`, `kind`, and `type` are fixed literals on each executable variant,
not independent free combinations. This prevents combinations such as a
Place-memory update when no such action exists. The base DTO contains only
fields genuinely shared across variants; fields such as a person's display
name do not belong in a universal node base. A `MemoryLog` has its own typed
memory-action variants and lifecycle rather than being treated as an ordinary
entity node. Relationship variants use local endpoint refs and only expose
relationship types approved for that state; structural links owned by a
create operation are written by that operation, not exposed as arbitrary
edges. Backend owner identity and graph UUIDs are injected/resolved by the
handler and never appear in the model-facing schema.

Create and update are separate concrete variants with different required
fields. Delete is not exposed until its type-specific lifecycle and behavior
are explicitly specified. An update targets an existing local ref and carries
an explicit typed patch. A new observation normally creates a new MemoryLog;
editing an existing log requires a separately specified correction operation.

The plan and tool call should reuse the same concrete action DTO variants when
they represent the same action. The plan may wrap them in an ordered action
list with dependencies; the tool call carries one action. Do not define a
second untyped action payload that must later be translated by field-name
guessing.

Runtime composition is selection over the canonical registrations:

1. The concrete state defines its maximum allowed action variants.
2. A validated plan may narrow that set to the relevant operation/kind/type
   variants, but cannot widen it.
3. The toolbox compiles the selected variants into the single graph-action
   function schema and maps that function to the dispatcher.
4. The dispatcher calls the typed service for the matched variant and returns
   one annotated result DTO; failures follow the normal recoverable tool-error
   path.

No runtime-generated fields, arbitrary metadata, global mutable registry, or
duplicate handler-name mapping is introduced. If a selected schema cannot be
represented by the chosen provider's strict profile, that is a toolbox
configuration error to report before the provider call, not a reason to loosen
the domain DTO.

OpenAI function parameters support JSON Schema descriptions, enums, and nested
objects; strict mode requires closed objects and all properties to be
required, with nullable types for semantically optional values. The supported
schema subset also constrains union composition: keep the function parameter
root as an object, use only supported nested union forms, and verify the
compiled schema rather than assuming a Pydantic discriminator is provider
compatible. See [official function-calling guidance](https://developers.openai.com/api/docs/guides/function-calling)
and [Structured Outputs schema constraints](https://developers.openai.com/api/docs/guides/structured-outputs).

## OpenAI function declaration adapter

The client compiles `ToolDefinitionDTO` and its `input_model` into the
canonical OpenAI-style function shape used at the client boundary. The
provider adapter translates that declaration to the selected API. Its semantic
content is:

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

For Chat Completions, the client boundary uses this wrapper:

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

Agentic states, tool registrations, and domain handlers never branch on this
provider shape.

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
Named toolboxes are purpose-specific. For graph actions, a toolbox may be
composed for a state invocation from the bounded predeclared variants and
narrowed by that invocation's validated plan:

```text
conversation_entry_toolbox
memory_query_toolbox
memory_creation_toolbox
```

A state receives the toolbox composed for its purpose and invocation. The
runtime dispatches a provider call using the registered tool definition and
handler in that toolbox. It does not dynamically discover arbitrary tools or
map a second string such as `handler_key` to an executable. Filtering selects
existing typed registrations; it does not create new action semantics.

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
