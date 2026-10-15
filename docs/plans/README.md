# Plans

This folder owns detailed, multi-wave work plans. Technical and functional
documentation remains the source of truth for design; plans link to those
owners and describe the work needed to reach the agreed target.

## Plan structure

Each plan contains wave folders; each wave contains issue folders; each issue
contains task Markdown files. Every folder has a `README.md` defining its
scope, indexing its contents, and linking relevant dependencies. A task file
should be actionable and identify its code/DTO boundaries, dependencies, and
acceptance evidence where known.

## Status tracking

Plan, wave, issue, and task files use one manually maintained `Status` value:
`Not started`, `In progress`, `Blocked`, or `Done`. Parent statuses are updated
explicitly; they are not calculated automatically. This tracks work progress,
not whether a source file is approved for reuse.

## File census format

Each source-file assessment uses the same brief fields:

1. **Current role** — what the file does today.
2. **Useful signal** — behavior, data meaning, or a contract worth considering.
3. **Do not port** — implementation or assumptions not to carry into the new layer.
4. **Treatment** — one of the agreed classifications, with evidence or an open
   question when needed.

The census assesses value; it does not authorize reuse. New agentic behavior
must follow the accepted technical specification.

## Plans

- [Agentic framework rebuild](agentic-framework-rebuild/README.md): census the
  current agentic pipeline and its integrations before defining implementation
  waves. Wave 0 is the only scoped wave so far; later waves require the census
  findings and product/technical decisions.
