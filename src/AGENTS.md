# Source code instructions

Use these canonical documents before making structural or AI-flow changes:

- [Technical principles](../docs/requirements/technical/technical-principles.md)
- [Dependency-oriented module design](../docs/requirements/technical/dependency-oriented-module-design.md)
- [Documentation conventions](../docs/documentation-conventions.md)
- [AI engineering index](../docs/ai-engineering/README.md)
- [Deterministic agentic workflows](../docs/architecture/deterministic-agentic-workflows.md)
- [Memory-ingestion workflow map](../docs/architecture/memory-ingestion-workflow-map.md)

Keep base models and contract classes separate from operating or functional
classes. Put models and contracts in a scope-specific `models.py`; put services,
states, workflows, handlers, and other behavior in separate purpose-named
modules.

Annotate every function and method with parameter and return types; explicitly
type class attributes when their types are not clear. Add concise docstrings to
main functions and classes, and document important methods with the contextual
information required by [Dependency-oriented module
design](../docs/requirements/technical/dependency-oriented-module-design.md).

When an implementation change alters documented behavior, update its canonical
documentation owner and relevant index in the same change. Do not introduce
unrequested requirements or parallel sources of truth.

For user-facing explanations of code changes, include enough context for a
reader who may not know the referenced modules or code paths.
