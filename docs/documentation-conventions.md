# Documentation conventions

## Purpose

Documentation is an engineered product surface. It must be navigable, current,
and explicit about what is a decision, a plan, a reference, or historical
context.

## Directory contract

Every directory under `docs/` must contain a `README.md` that states:

1. the directory's purpose and ownership;
2. an index of its direct documents and subdirectories;
3. the status of material that is provisional, superseded, or historical;
4. the intended reader when that is not obvious.

When a directory is added, renamed, or gains a material document, its README
must be updated in the same commit. Root-level [docs/README.md](README.md) is
the entry point and links the top-level areas.

## Document contract

Each substantive document starts with a clear purpose. It distinguishes:

- **Decision**: a chosen, binding direction.
- **Specification**: a behavior or contract implementation must satisfy.
- **Plan**: ordered future work; it is not proof of implementation.
- **Reference**: useful evidence or prior material that is not canonical.
- **Historical**: retained context that must not guide new implementation.

Avoid duplicated authoritative rules. Link to the canonical document instead.
Use relative Markdown links and update inbound links when relocating a file.

## Human-first writing

Write for a reader who may not know the codebase, its names, or the history
behind a decision. Give enough context for each page or section to make sense
on its own, and explain code references when they matter to the reader. Prefer
clear prose; use concise bullets when they make information easier to scan.
Each bullet should carry enough context to be understood without relying on
unstated knowledge. Keep explanations concise when that does not remove useful
context.

## Engineering documentation baseline

The annotation-first rule is a repository-wide development standard: every
function and method has parameter and return type annotations, and class
attributes have explicit types where their types are not otherwise clear. Any
new interface across model, provider, runtime, API, domain, or persistence
boundaries requires an explicit typed contract. Untyped dictionaries may exist
only at an external parsing boundary and must be converted immediately to the
relevant DTO.

Module layout, inheritance, acyclic imports, and contextual documentation for
important methods are governed by the binding
[dependency-oriented module design](requirements/technical/dependency-oriented-module-design.md).

## Scope ownership

The binding rule for accepted scope and minimum design is maintained in
[Technical Principles](requirements/technical/technical-principles.md#explicit-scope-and-minimum-design).
