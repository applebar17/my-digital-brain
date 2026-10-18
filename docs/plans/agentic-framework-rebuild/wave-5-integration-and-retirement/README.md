# Wave 5 — application integration and retirement

**Status: Not started**

## Outcome

Compose the new states/workflows behind the existing user-facing boundaries,
verify representative flows end to end, then move the remaining supported
application source/imports to `product` and delete superseded `my_digital_brain`
runtime code. Frontend handoff is validated here as part of feature integration,
not as an independent clarification architecture.

## Issues

- [Issue 5.1 — compose API/chat runtime and verify end-to-end flows](issue-5.1-application-integration/README.md)
- [Issue 5.2 — cut over the source namespace and retire old runtime](issue-5.2-namespace-cutover-and-retirement/README.md)

## Dependencies

- Depends on required states, capabilities, and workflows from Waves 1–4.
- Stable endpoint and UI contracts are inventoried in
  [Wave 0 Issue 0.3](../wave-0-census/issue-0.3-integration-census/README.md).
- Preserve existing API semantics where accepted; do not introduce a
  compatibility runtime or duplicate transcript owner.

## Exit evidence

- A user can exercise the agreed chat/query and ingestion flows through the
  frontend, including any clarification that those flows require.
- Functional tool/state results are not shown as final assistant messages.
- Supported imports use `product`; the old source tree and obsolete agentic
  paths are removed with no compatibility forwarding layer.
- Repository tests/configuration pass, with `logs/` remaining uncommitted.
