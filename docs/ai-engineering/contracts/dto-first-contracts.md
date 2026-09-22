# DTO-first contract baseline

## Decision

All model-facing structured data and all tool boundaries use explicit Pydantic
DTOs. The backend never treats an untyped `dict`, `**kwargs`, or a provider SDK
object as an application contract.

The provider adapter is the only layer allowed to parse provider-native tool
call objects. It converts them into `ToolCallDTO`; the runtime validates and
dispatches them through a registered `ToolDefinition`.

## Canonical DTOs

The names below are the target vocabulary. Exact module paths will be decided
by the implementation plan, not invented independently by feature code.

```python
class ToolCallDTO(BaseModel):
    provider_call_id: str
    name: str
    arguments_json: str

class ToolErrorDTO(BaseModel):
    code: str
    message: str
    hint: str | None = None
    retryable: bool
    details: dict[str, JsonValue] = Field(default_factory=dict)

class ToolOutputDTO(BaseModel):
    status: Literal["ok", "recoverable_error", "error", "awaiting_input"]
    data: BaseModel | None = None
    error: ToolErrorDTO | None = None

class ToolDefinition(BaseModel):
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
```

`provider_call_id` is immutable and provider-issued. For Chat Completions it
normalizes the assistant tool call's `id`; for Responses it normalizes the
function call's `call_id`. The adapter owns this difference. All other layers
refer only to `provider_call_id`.

Every model-facing DTO has `extra="forbid"`, precise field descriptions, and
the smallest required shape. Domain records, database UUIDs, provenance, and
transport metadata are backend-owned and must not be requested from the model.

The provider-neutral definition, semantic field-schema requirements,
OpenAI-compatible declaration compilation, and toolbox composition are defined
in [tool definition and toolbox contracts](tool-definition-and-toolbox.md).

## Tool registration and invocation

A registered tool is a typed unit:

```text
ToolDefinition<InputDTO, OutputDTO>
  -> provider JSON schema generated from InputDTO
  -> raw provider arguments parsed once into InputDTO
  -> handler(context, input_dto) -> OutputDTO | ToolOutputDTO
  -> one serialized ToolOutputDTO matched to provider_call_id
```

The handler accepts its validated DTO, not loose keyword arguments. A tool may
be implemented by an LLM-backed child session, but its outer handler still has
the same rule: it returns one `ToolOutputDTO` to the parent call after the child
finishes or pauses.

## Validation and failure behavior

1. Invalid JSON or invalid DTO input becomes one typed tool error output.
2. Domain validation failure becomes one typed tool error output.
3. Unexpected handler exception becomes one typed tool error output and is
   logged with its technical traceback.
4. The error output is appended to the same session using the original
   `provider_call_id`; it is never returned as the user-facing final response.
5. A retryable error gives the model an actionable explanation and lets the
   normal loop continue within its bounded budget.

`ToolErrorDTO.message` and `hint` are written for both a human reader and the
model. They state the violated condition, valid alternatives when useful, and
the appropriate next action. Raw Pydantic errors and exception strings belong
in diagnostic details, not as the only model instruction.

## Structured model outputs

Structured output is separate from tool invocation. A state that needs a final
structured artifact declares an output DTO; the provider adapter parses it;
the runtime applies structural then semantic validation. Recoverable failures
are appended as a user repair message to the same state-local history and
retried within a small explicit budget.

Do not use a fake submission tool merely to return a structured final object.
