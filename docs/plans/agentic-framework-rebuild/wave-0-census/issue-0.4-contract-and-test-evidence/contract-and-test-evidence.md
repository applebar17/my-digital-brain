# Map contracts and test evidence

**Status: In progress**

## Objective

Trace the currently observable agentic behaviors and DTO boundaries to
production code, callers, tests, and the canonical documentation. Record
coverage and mismatches without treating current code as the target design.

## Evidence to inspect

- Session/tool transcript lifecycle, including provider call IDs, tool
  failures, nested agent calls, and continuation.
- State invocation/result and structured-output contracts.
- Shared versus state-local history and persisted chat history.
- Clarification pause, answer submission, and resumed execution.
- Ingestion stages, reference context, planned writes, and graph mutations.
- Chat response, activity/progress, and frontend API DTOs.
- Prompt selection, runtime context insertion, and structured model outputs.
- Existing tests under `tests/` covering agentic, chat, clarification, and
  ingestion behavior.

## Initial test index

| Test file | Evidence area |
| --- | --- |
| `tests/test_agentic_foundation.py` | Model-facing context/ref/planning DTOs, prompt registry assumptions. |
| `tests/test_agentic_runtime.py` | Root/child handoff, matched tool outputs, failure recovery, clarification resume, structured calls. |
| `tests/test_agentic_history.py` | Shared/state-local projection, history promotion and summaries. |
| `tests/test_agentic_tool_bindings.py` | Tool schemas, permissions, graph writes, clarification handoff and errors. |
| `tests/test_agentic_query_foundation.py` | Deterministic memory retrieval and answer context. |
| `tests/test_agentic_risk_foundation.py` | Contradiction, profile, maintenance behavior and state configs. |
| `tests/test_chat_runtime.py` | Chat API response persistence, runtime calls, pending/resume. |
| `tests/test_chat_activity.py` | User-facing activity titles and rendering contract. |
| `tests/test_chat_agentic_renderer.py` | Final answer/clarification/result mapping. |
| `tests/test_interactive_ingestion_clarifications.py` | Ingestion pause and continuation behavior. |
| `tests/test_clarification_toolbox.py`, `tests/test_clarification_contracts.py` | Clarification tools, DTOs, options, and output behavior. |
| `tests/test_ingestion_runtime.py` | End-to-end stage sequence, context handoff, and resolution planning. |
| `tests/test_ingestion_write_execution.py` | Candidate→write mapping, graph writes, idempotency, vectorization outcomes. |
| `tests/test_ingestion_contracts.py` | Ingestion DTO schema/validation behavior. |
| `tests/test_ingestion_planning_scaffolding.py` | Planning contracts and prompt context. |
| `tests/test_ingestion_extractors.py` | Structured extraction schemas and extractor behavior. |
| `tests/test_memory_ingestion_prompt_hardening.py` | Ingestion prompt behavior and constraints. |

The tests describe current expectations, not automatic approval of every
assertion as a target requirement. For each test, identify the user-visible or
backend contract it protects; mark implementation-only assertions for rewrite
or removal once the replacement behavior is specified.

## Initial behavioral findings

- The ingestion pipeline is deterministic in its stage ordering today, while
  reasoning, planning, extraction, and resolution are selected LLM calls. This
  is evidence for functional responsibilities, not a decision that the current
  stage structure must be preserved.
- Graph mutation is a distinct deterministic write-plan/executor boundary;
  candidate extraction/proposals are not themselves proof that a durable write
  occurred. Census that mapping and failure/result contract explicitly.
- Clarification is nested within execution and must preserve a resumable caller
  interaction. Current pending DTOs can originate from both AI-session and
  agentic-state result types; their ownership needs consolidation.
- Tool call/provider transcript correlation is represented in the current AI
  session layer and has regression tests. Compare current callers and data
  crossings with the required `ai_clients` target and canonical tool-calling
  contract; do not reopen the client-layer selection.
- The current source has `AgenticStateRunner`/`AgenticHistoryService`, whereas
  the target docs specify `BaseAgenticState`/`AgenticHistorySession`. Treat this
  as a genuine implementation gap to plan for, not as an already completed
  migration.

## Required output

For each behavior, cite the owning code and tests, classify it as required
observable behavior / backend contract / internal implementation, and note any
missing or contradictory evidence. These findings become inputs to the later
implementation-wave plan; do not define those waves in this task.
