# Prompt lifecycle and versioning

## Decision

Every LLM-backed state receives a system prompt from an explicitly versioned,
file-backed template. A state selects an exact prompt reference; a registry
loads it; a renderer fills its declared runtime slots; and the resolved prompt
identity is recorded with the state run.

Prompt files define model behavior and named context slots. They do not own
tool declarations, provider requests, backend validation, execution order, or
database data.

This is deliberately a code-and-file design. Markdown files are the versioned
prompt source; typed Python configuration selects and renders them. A YAML
configuration layer is not needed at this stage.

## Source layout

The target application package layout is:

```text
src/my_digital_brain/prompts/
  README.md
  contracts.py
  registry.py
  renderer.py
  templates/
    conversation-entry/
      v1.system.md
    memory-query/
      v1.system.md
    memory-ingestion/
      v1.system.md
```

`templates/<prompt-id>/<version>.system.md` is the single source for a
production system-prompt body. The existing Python prompt constants are
migration material only: once a template is migrated, production code must not
also load a duplicate constant for that prompt.

The `README.md` in the application package indexes the contracts, rendering
syntax, template directory, and active prompt references. This follows the
project-wide documentation/scaffolding rule.

## Typed contracts

The exact Python module paths are implementation work. These are the required
semantics:

```python
class PromptReferenceDTO(BaseModel):
    """An immutable selection of one versioned system prompt."""

    prompt_id: str
    version: str


class PromptRenderContextDTO(BaseModel):
    """Named, already-rendered sections allowed to fill one prompt template."""

    values: dict[str, str]


class PromptSnapshotDTO(BaseModel):
    """Prompt identity recorded for one state run."""

    prompt_id: str
    version: str
    template_checksum: str
    rendered_checksum: str
```

`PromptRenderContextDTO` contains display-ready strings produced by dedicated
context renderers. It does not carry raw graph records, arbitrary Python
objects, provider objects, or a generic metadata dump. For example, a
reference-context renderer supplies `reference_inventory`; a retrieval-context
renderer supplies `retrieval_packet`.

The state configuration owns the `PromptReferenceDTO`. The concrete state or
its context builder owns the typed context package and converts it to the
limited render context. The registry never guesses a version or chooses a
"latest" prompt at runtime.

## Template syntax and rendering

Templates use only named placeholders in this form:

```md
## Known references
{{ reference_inventory }}
```

The renderer performs literal named substitution only. It does not evaluate
Python expressions, attribute paths, method calls, conditionals, loops, or
implicit object stringification. This preserves the intended f-string-like
configuration while keeping prompt files declarative and predictable.

For each render:

1. the registry resolves the explicit `(prompt_id, version)` to one Markdown
   file;
2. the renderer discovers its named placeholders;
3. it rejects a missing required name with a clear configuration error before
   an LLM call;
4. it substitutes the pre-rendered values and returns the final system text
   with a `PromptSnapshotDTO`.

The renderer does not invent defaults for missing context. A missing declared
slot is a state-configuration error, not an occasion to send an incomplete
prompt silently. Braces needed as ordinary prompt text are escaped according
to the chosen renderer's documented literal-brace convention.

## Runtime placement and traceability

The rendered template is the system instruction of an
`AgenticStateInvocationDTO`. The invocation request remains a separate final
`user` message in the state-local transcript, as defined by the
[agentic-state framework](../runtime/agentic-state-framework.md). History,
tool calls, and tool outputs remain provider-transcript messages; they are not
interpolated wholesale into the system template.

Each state run records its `PromptSnapshotDTO` in the run trace. This makes it
possible to identify exactly which template version and rendered content
identity influenced a behavior. Raw rendered prompt persistence is a separate
observability/privacy decision and is not introduced by this policy.

## Prompt authoring policy

System templates contain stable role, scope, behavioral guidance, definitions,
and a small number of targeted shots. Dynamic packets are injected in named,
clearly headed slots near the end of the template. The detailed writing rules
remain in [prompting guidelines](prompting-guidelines.md).

Prompt references are chosen by concrete agentic states and their preparation
configurations. Reasoning and planning preparation calls therefore have their
own explicit prompt references; they do not mutate or reuse a main-state prompt
implicitly.

## Migration rules

1. Create the versioned Markdown template from the current active prompt.
2. Bind its concrete state to an explicit `PromptReferenceDTO`.
3. Move dynamic values into named render slots backed by dedicated context
   renderers.
4. Record the prompt snapshot in the state run.
5. Move the final caller and delete the old Python constant and alternate
   loading path in the same migration wave.

No prompt may have both a file-backed and code-constant production source.

## Verification

Prompt tests cover template resolution by exact version, missing-slot
diagnostics, literal-brace behavior, rendering fixtures for each active state,
and snapshot identity changes when either a template or rendered content
changes. Behavioral/evaluation tests remain a later, separate concern.
