# Active Prompt Inventory

This inventory maps active agentic prompts to their visible context, tools, and
prompt-only behavior. Static prompts stay lean; runtime packets, tool schemas,
and structured-output schemas carry the detailed contract.

| Prompt | Goal | Visible context | Tools | Output | Prompted behavior |
| --- | --- | --- | --- | --- | --- |
| `conversation_entry` | Route chat to direct answer, memory query, or memory ingestion. | Conversation messages and available top-level tools. | `query_memory`, `ingest_memory`. | Assistant text or one top-level tool call. | Choose the smallest route; keep graph update out of the top-level surface. |
| `memory_query` | Answer questions from stored memory. | User question, hydrated retrieval/context packets, seed hints. | Read-only graph/context/timeline/map/evidence tools. | Grounded answer context. | Retrieve before answering graph-dependent questions; no clarification. |
| `memory_ingestion` | Produce high-level reasoning inventory for memory storage. | History, hydrated graph context, alias/candidate packets. | Read helpers and clarification when blocked by missing meaning. | `MemoryIngestionReasoning`. | Stay high level; no refs or executable actions; carry aliases and irrelevant details. |
| `memory_node_planning` | Plan node resolution/creation. | Reasoning inventory, known refs, duplicate candidates. | Structured-output planning provider. | `NodeMemoryPlan` plus `NodePlanPacket`. | Resolve aliases/duplicates before proposing nodes; node boundaries. |
| `memory_log_planning` | Plan MemoryLogs and context records. | Reasoning inventory, node plan packet, refs, irrelevant details. | Structured-output planning provider. | `MemoryLogMemoryPlan` plus `MemoryPlanPacket`. | Split dense memories; keep weak co-presence as involvement. |
| `memory_log_extraction` | Extract one backend-facing MemoryLog draft from a planned memory-log target. | Purpose packet, compact graph/entity context, current planning action, current target, time, and explicit user message with the action payload. | Read helpers and clarification when extraction is blocked. | `MemoryLogDraftBatch`. | Preserve stable `MEMORY_LOG_*` refs; no writes; no durable relationship inference from weak co-presence. |
| `memory_edge_planning` | Plan durable edges/context links. | Reasoning inventory, node packet, memory packet, refs, relationship candidates. | Structured-output planning provider. | `EdgeMemoryPlan`. | Use ref endpoints only; require strong edge evidence. |
| `memory_creation` | Execute one creation-oriented plan action. | Current action, action packet, history, relevant refs and prior summaries. | Deterministic read/write tools, graph update child tool, clarification. | Compact tool/result payload. | Use tools for writes; recover from validation errors; clarify only when blocked. |
| `graph_update` | Apply non-destructive graph updates. | Guidelines, desired work, target hints, history, graph context. | Resolve/read/write tools and clarification. | Compact tool/result payload. | Resolve targets, use write tools, recover from validation errors. |
| `contradiction_review` | Judge grounded contradiction doubts. | Proposed write, affected refs, evidence, graph context. | Evidence/read tools and clarification. | `ContradictionJudgeResultContext`. | Distinguish contradiction, ambiguity, and correction. |
| `reasoning_checkpoint` | Produce reusable reasoning notes for generic subprocesses. | Purpose guidelines, process context, messages. | Read tools and clarification. | `ReasoningCheckpointResultContext`. | Highlight only decision-relevant doubts, aliases, and gaps. |
| `planning_checkpoint` | Produce reusable ordered process actions. | Caller goals, reasoning notes, context packets. | Read tools and clarification. | `PlanningTransformResultContext`. | Keep plans concise and dependency-aware. |

## Removed Prompt Surfaces

These prompt directories are not active runtime surfaces and should not be loaded
by production code: `pending_process_review`, `correction_intake`,
`correction_proposal`, `ingestion_planner`, `clarification_classifier`,
`profile_memory_extraction`, `maintenance_review`, `query_retrieval_planning`,
and `answer_generation`.

If one of those capabilities becomes active again, add a new state/tool owner and
new lean prompt instead of reviving old scaffold text.
