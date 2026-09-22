# Dependency-oriented module design

## Purpose and status

**Binding coding standard.** This document defines how modules, classes, and
important methods are organized. It makes the code readable in the same
direction as its dependencies: from stable contracts to concrete work and then
to composition.

There is no single universally standard name for this style. It combines
layered architecture, an acyclic dependency graph, dependency inversion, and
template-method inheritance. In this repository we call it
**dependency-oriented module design**.

It complements the repository-wide DTO-first rule in
[Documentation conventions](../../documentation-conventions.md) and the
existing [technical principles](technical-principles.md).

## Dependency direction

Dependencies must form a directed acyclic graph. A lower layer never imports a
higher layer in order to complete its work.

The usual order is:

1. **Contracts**: DTOs, enums, protocols, errors, and small value objects.
   They do not import services, adapters, or application orchestration.
2. **Pure helpers**: validation, normalization, rendering, and conversion that
   depend only on contracts and standard/library concerns.
3. **Base abstractions**: abstract classes and reusable template methods that
   depend on contracts and pure helpers.
4. **Concrete implementations**: provider adapters, repositories, and domain
   services that implement a stable abstraction.
5. **Orchestration**: use-case and runtime classes that coordinate concrete
   capabilities through their contracts.
6. **Composition boundaries**: factories, dependency injection, CLI/API
   startup, and configuration. These are the only places that choose concrete
   implementations.

For example, an AI runtime should read as:

`DTOs and protocols -> tool/provider helpers -> abstract adapter/runtime base -> OpenAI or Azure adapter -> session orchestration -> application composition`.

If a lower layer needs behavior from a higher layer, introduce a protocol or
DTO in the lower layer and make the higher layer implement it. Do not solve the
problem with a reverse import, runtime import, mutable global registry, or
untyped dictionary.

## Module and class organization

Keep a module understandable top-to-bottom. Its declarations should normally
appear in dependency order:

1. imports and module constants;
2. type aliases, DTOs, protocols, and errors owned by the module;
3. pure helpers;
4. base or abstract classes;
5. concrete subclasses;
6. factories or explicitly exported entry points.

Within a class, put public entry methods first, followed by the private methods
they invoke in approximate execution order. A reader should be able to follow
the normal path without jumping between unrelated files or methods. A class
that cannot be ordered this way usually owns too many responsibilities and
should be split at a real contract boundary.

Apply inheritance only when a subclass is genuinely substitutable for a base
contract and shares stable lifecycle behavior. A base class may own a template
method while subclasses implement explicit extension points. Prefer composition
when behavior is optional, varies by use case, or would require subclasses to
override unrelated methods.

Circular imports are design defects. `TYPE_CHECKING` imports are allowed only
for annotations, never to hide runtime coupling. Local imports are not a
general workaround; use them only for a documented, unavoidable external
dependency and leave the application dependency graph acyclic.

## Contextual documentation for important methods

Important methods require a compact contextual docstring. It documents the
method's role in the system, not its implementation line by line and never an
agent's chain-of-thought.

Use it for public entry points, state transitions, tool dispatch, provider
translation, persistence operations, external I/O, and non-obvious validation
or recovery paths. It is unnecessary for trivial DTO accessors, obvious small
helpers, and standard protocol implementations whose contract already says
enough.

The docstring should state, where applicable:

- **Purpose**: the business or runtime operation performed.
- **Contract**: important input, output, and error guarantees.
- **Immediate dependencies**: the first-level collaborators it calls or whose
  state it changes; name contracts/classes, not distant transitive internals.
- **Side effects**: persistence, transcript changes, network calls, or emitted
  events.

Example:

```python
def execute_tool_call(
    self,
    call: ToolCallDTO,
    transcript: SessionTranscript,
) -> ToolOutputDTO:
    """Validate and execute one provider-issued tool call.

    Dependencies:
        - ``ToolRegistry`` resolves the typed tool definition.
        - ``ToolExecutor`` validates the input DTO and invokes its handler.
        - ``SessionTranscript`` receives one output matched to the provider
          call ID.

    Side effects:
        Appends the output to ``transcript``. This method does not call the
        provider; the enclosing session loop performs that continuation.
    """
```

The named dependencies must remain true. Update this documentation in the same
change when the method's immediate collaborators or side effects change.

## AI runtime application

For the AI runtime, this standard has concrete consequences:

- Provider-specific message shapes end at the provider adapter; the generic
  runtime consumes and produces canonical DTOs only.
- Tool registration and execution are lower-level capabilities. The session
  loop coordinates them but does not know ingestion, graph, or UI details.
- A provider adapter, tool executor, and session runtime must not instantiate
  one another directly. Their assembly belongs to a composition boundary.
- A child agent implements the same typed tool contract as any other tool; it
  does not introduce a second session-loop path.
- Tool call IDs, transcript state, and continuation behavior are owned by
  explicit DTOs and services, not ad hoc method-local dictionaries.

The [AI engineering foundations](../../ai-engineering/foundations/README.md)
apply this standard to the clean-slate migration. The detailed migration order
remains in the [client-runtime rebuild plan](../../ai-engineering/migration/client-runtime-rebuild-plan.md).

## Review checklist

Before accepting a substantial module or method change, verify:

- imports flow toward lower, stable layers only;
- application payloads cross boundaries as annotated DTOs;
- inheritance represents substitution and stable shared behavior;
- a reader can follow the main method path in declaration order;
- important methods identify their immediate collaborators and side effects;
- no circular import, legacy shim, hidden fallback, or untyped mapping was
  introduced to bypass a boundary; and
- composition of concrete implementations occurs at an explicit application
  boundary.
