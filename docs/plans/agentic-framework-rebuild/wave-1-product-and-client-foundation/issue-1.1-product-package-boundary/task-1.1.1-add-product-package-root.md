# Task 1.1.1 — add the target package root

**Status: Done**

## User story

As a developer, I want new runtime code to import from `product`, so rebuilt
framework and application code can evolve independently of the current
`my_digital_brain` implementation.

## What and why

Add the minimal package root and configure source discovery and local tooling
to recognize it. Do not move the old package or add a forwarding alias in this
task. A package-name-only smoke test is not useful coverage here.

## Where

- `src/product/` package root and minimal package initializer.
- Project packaging/configuration.

## Functional communication DTOs

None. This task creates a Python import boundary only.

## Dependencies and acceptance

- Depends on Issue 0.2 census completion.
- Wheel/package discovery includes `product` while retaining the existing
  package during migration.
- Existing `my_digital_brain` imports and application behavior are unchanged.
- No compatibility alias makes either namespace the hidden owner of the other.
