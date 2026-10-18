# Task 5.2.2 — remove superseded package and verify clean cutover

**Status: Not started**

## User story

As a maintainer, I want the obsolete agentic runtime and old Python package
removed after callers migrate, so future development has one clear source of
truth and no accidental legacy imports.

## What and why

Delete retired modules, exports, duplicated prompts/configuration, and dead
tests only after search and test evidence confirms they have no target caller.
Do not keep forwarding shims or deprecated alternatives.

## Where

- Superseded `src/my_digital_brain/` modules and obsolete runtime/tool imports.
- Package and test configuration, docs indexes, startup scripts, and ignore
  rules as applicable.

## Functional communication DTOs

None introduced. Verify the canonical `product` DTO contracts remain the only
ones used for provider, state, tool, application, and API communication.

## Dependencies and acceptance

- Depends on Task 5.2.1 and clean E2E/runtime test results.
- No production or test imports remain from `my_digital_brain`.
- No duplicate runtime, compatibility aliases, or obsolete prompt/tool registry
  remains.
- Logs stay excluded from commits; full project test suite and packaging pass.
