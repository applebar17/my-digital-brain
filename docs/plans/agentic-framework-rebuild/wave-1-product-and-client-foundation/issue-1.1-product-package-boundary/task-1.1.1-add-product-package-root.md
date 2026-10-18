# Task 1.1.1 — add the target package root

**Status: Not started**

## User story

As a developer, I want new runtime code to import from `product`, so rebuilt
framework and application code can evolve independently of the current
`my_digital_brain` implementation.

## What and why

Add the minimal package root and configure source discovery, test imports, and
local tooling to recognize it. Do not move the old package or add a forwarding
alias in this task.

## Where

- `src/product/` package root and minimal package initializer.
- Project packaging/configuration and focused import smoke tests.

## Functional communication DTOs

None. This task creates a Python import boundary only.

## Dependencies and acceptance

- Depends on Issue 0.2 census completion.
- `product` imports in the configured development and test environments.
- Existing `my_digital_brain` imports and application behavior are unchanged.
- No compatibility alias makes either namespace the hidden owner of the other.
