# Issue 1.2 — adopt and verify the selected AI client layer

**Status: Not started**

Place the already-selected `ai_clients` package under the target namespace and
confirm its real provider/tool behavior against the accepted contracts. This
is focused adoption, not a client rewrite or second tool-loop implementation.

## Tasks

- [Task 1.2.1 — locate the client package under `product`](task-1.2.1-relocate-ai-clients.md)
- [Task 1.2.2 — verify provider calls and tool continuation](task-1.2.2-verify-client-tool-loop.md)

## Dependencies

- [Required client-layer assessment](../../../../ai-engineering/migration/reference-ai-clients-assessment.md)
- [Tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md)

## Functional communication DTOs

Provider-neutral request, response, tool-call, and tool-output DTOs remain
owned by `ai_clients`. Its normalized call identifier pairs each mapped
function result with the original model request; agentic/application states do
not construct provider transcript messages.
