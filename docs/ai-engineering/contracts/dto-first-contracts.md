# DTO-first contract baseline

## Decision

All model-facing structured data and all tool boundaries use explicit Pydantic
DTOs. The backend never treats an untyped `dict`, `**kwargs`, or a provider SDK
object as an application contract.

The provider adapter is the only layer allowed to parse provider-native tool
call objects. It converts them into `ToolCallDTO`; the runtime validates and
dispatches them through a registered `ToolDefinitionDTO`.

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
    details: dict[str, Any] = Field(default_factory=dict)

class ToolOutputDTO(BaseModel):
    status: Literal["ok", "error"]
    data: dict[str, Any] | None = None
    error: ToolErrorDTO | None = None

class ToolDefinitionDTO(BaseModel):
    name: str
    description: str
    input_model: type[BaseModel]
```

Every invocation returns one `ToolOutputDTO`: successful results use
`status="ok"` and `data`; failures use `status="error"` and `error`. The
framework resumes the caller with either result; it does not encode a retry
policy in the DTO. A clarification pause has no tool output until the original
invocation resumes.

`provider_call_id` is immutable and provider-issued. For Chat Completions it
normalizes the assistant tool call's `id`; for Responses it normalizes the
function call's `call_id`. The adapter owns this difference. All other layers
refer only to `provider_call_id`.

Every DTO requested as structured model output has `extra="forbid"`, precise
field descriptions, and the smallest required shape. Backend-constructed tool
result DTOs do not need that input-validation setting. Domain records, database
UUIDs, and transport metadata are backend-owned and must not be requested from
the model.

## Proposal, command, and persisted-record boundary

An LLM returns a semantic proposal DTO: input-grounded content, model-facing
references, and only the explicit fields required for the receiving state. It
does not return storage identifiers, timestamps, lifecycle
state, or arbitrary metadata.

The receiving backend state validates that proposal and creates an explicit,
purpose-specific command DTO for a deterministic write. The command contains
only the fields the target service needs. The service enriches the persisted
record with backend-owned identifiers and storage metadata required by that
domain object.

```text
model proposal DTO
  -> state validation and reference resolution
  -> typed deterministic command DTO
  -> persisted domain record
```

Do not introduce a generic graph-write plan, an untyped action list, or a
catch-all candidate object to bridge these responsibilities. A new semantic
need receives a small state-local proposal and an explicit target command.

The MVP ingestion contract does not require a persisted source record or the
identifier of the original chat message. Normalized text or a transcript may
be passed through the workflow as transient model context. A specific
integration may later define its own artifact-retention contract, but that is
not a baseline DTO or graph-write requirement.

The provider-neutral definition, semantic field-schema requirements,
OpenAI-compatible declaration compilation, and toolbox composition are defined
in [tool definition and toolbox contracts](tool-definition-and-toolbox.md).

## Tool registration and invocation

A registered tool is a typed unit:

```text
ToolDefinitionDTO<InputDTO>
  -> provider JSON schema generated from InputDTO
  -> raw provider arguments parsed once into InputDTO
  -> typed handler(input_dto) -> OutputDTO
  -> client wraps success/error as ToolOutputDTO
  -> one serialized ToolOutputDTO matched to provider_call_id
```

The handler accepts its validated DTO, not loose keyword arguments. Its
annotated return type is the successful domain output; it is not repeated in
the tool definition. Dependencies are bound during toolbox composition rather
than carried in a generic per-call context DTO. The client owns the single
provider-facing `ToolOutputDTO`: success contains the JSON-compatible output
data, while invalid arguments and handler failures contain one error. The
caller resumes after either result. A child state that pauses for human input
pauses the session; it does not create a pending tool-result status.

## Validation and failure behavior

1. Invalid JSON or invalid DTO input becomes one `ToolOutputDTO(status="error")`.
2. Domain validation failure becomes one `ToolOutputDTO(status="error")`.
3. Unexpected handler exception becomes one `ToolOutputDTO(status="error")` and is
   logged with its technical traceback.
4. The error output is appended to the same session using the original
   `provider_call_id`; it is never returned as the user-facing final response.
5. The error message and hint give the model useful context while the normal
   tool loop continues within its configured call cap.

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
