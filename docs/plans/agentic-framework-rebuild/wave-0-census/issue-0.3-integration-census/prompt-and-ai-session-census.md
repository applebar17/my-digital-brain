# Census prompts and the AI-session boundary

**Status: Complete**

This census records the runtime prompt selection and the active path from an
agentic-state invocation to a provider response. The accepted prompt lifecycle,
agentic-state, and tool-calling specifications remain the target; current code
is migration evidence only.

## Prompt sources

`AgenticStateConfig` defaults every configured state to prompt version `v1`.
`AgenticStateRunner` loads the `(prompt_id, prompt_version)` pair from
`PromptRegistry`, then adds runtime context. The runtime may override the
prompt ID/version in invocation metadata. `MemoryIngestionRuntimeService`
selects the node-, memory-log-, and edge-planning prompt IDs for its phases.

| Prompt ID (`v1`) | Configured state or caller | Current production template source |
| --- | --- | --- |
| `conversation_entry` | `CONVERSATION_ENTRY` | `prompts/active.py` constant |
| `reasoning_checkpoint` | `REASONING_CHECKPOINT` | `prompts/active.py` constant |
| `planning_checkpoint` | `PLANNING_CHECKPOINT` | `prompts/active.py` constant |
| `memory_log_extraction` | `MEMORY_LOG_EXTRACTION` | `prompts/active.py` constant |
| `memory_query` | `MEMORY_QUERY` | `prompts/active.py` constant |
| `memory_ingestion` | `MEMORY_INGESTION` | `prompts/active.py` constant |
| `memory_node_planning` | Ingestion runtime node-planning phase; invokes `MEMORY_INGESTION` state with an override | `prompts/active.py` constant |
| `memory_log_planning` | Ingestion runtime memory-log-planning phase; invokes `MEMORY_INGESTION` state with an override | `prompts/active.py` constant |
| `memory_edge_planning` | Ingestion runtime edge-planning phase; invokes `MEMORY_INGESTION` state with an override | `prompts/active.py` constant |
| `memory_creation` | `MEMORY_CREATION` | `prompts/active.py` constant |
| `graph_update` | `GRAPH_UPDATE` | `prompts/active.py` constant |
| `contradiction_review` | `CONTRADICTION_REVIEW` | `prompts/active.py` constant |
| `profile_duplication` | `PROFILE_DUPLICATION` | `prompts/active.py` constant |
| `clarification_agent` | `CLARIFICATION_AGENT` | `prompts/active.py` constant |
| `profile_memory_extraction` | No configured state/call site found; appears in registry and tests | Default registry returns `prompts/active.py` constant; matching Markdown file is shadowed |
| `owner_profile` | No configured state/call site found | Constant registered, but no `PromptRegistry.load` call found |

The registry uses `ACTIVE_PROMPT_TEMPLATES` for default-registry `v1` lookups
before consulting Markdown files. The four files under `prompts/templates/`
are `answer_generation`, `maintenance_review`, `profile_memory_extraction`,
and `query_retrieval_planning`. None is selected by a configured runtime state;
the `profile_memory_extraction` file is shadowed by its active constant. These
are not evidence of four additional live state prompts.

### Prompt package file dispositions

| File/group | Current role | Useful signal | Do not port | Treatment |
| --- | --- | --- | --- | --- |
| `src/my_digital_brain/prompts/models.py` | `PromptTemplate` identity/version/template model | Existing prompt identity and version concepts | Assume it already implements the accepted reference/render/snapshot DTO contracts | Rebuild against prompt lifecycle spec |
| `src/my_digital_brain/prompts/registry.py` | Constant-first lookup and placeholder rendering | Placeholder rendering and clear missing-variable errors | Constant fallback/shadowing as a second production source | Replace with exact configured file lookup per accepted spec |
| `src/my_digital_brain/prompts/active.py` | Current production prompt bodies and ID map | Prompt behavior that remains functionally approved | Python constants as parallel production prompt copies | Migrate approved prompt content to versioned Markdown, then retire constants |
| `src/my_digital_brain/prompts/memory_ingestion.py` | Re-export/compatibility path for prompt constants | Evidence of the old ingestion prompt import surface | Duplicate prompt source or compatibility layer without an active consumer | Retire after callers move |
| `src/my_digital_brain/prompts/clarification_policy.py` | Shared clarification policy/examples concatenated into prompt constants | Shared clarification behavior where still accepted | Implicit prompt assembly that duplicates policy across versioned templates | Move accepted policy to the owning versioned templates without duplicate sources |
| `src/my_digital_brain/prompts/templates/` | Four file-backed templates, only one sharing an ID with a constant | Candidate prompt content requiring review | Unused or shadowed templates as though active | Verify content during prompt migration; retain only explicitly selected versions |

## Active AI-session/provider boundary

| Layer | Active responsibility and path | Migration evidence / target treatment |
| --- | --- | --- |
| Application entry | Chat runtime calls `AgenticRuntime`; runtime invokes `AgenticStateRunner` | Preserve the necessary higher-level integration boundary; census is in [integration file census](integration-file-census.md) |
| Agentic state | `AgenticStateRunner` builds state prompt/context and creates `LLMSessionRequest` | Replace with the documented state layer; it should delegate provider request/tool iteration to `ai_clients` |
| Session/tool loop | `LLMSessionRunner` repeatedly calls a one-request transport, dispatches through `ToolExecutor`, appends tool results, handles continuation and structured-output repair | This is the current separate tool-loop implementation. Do not port as another loop beside `LLMInterfaceCore`; compare edge behavior to the accepted [tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md) |
| Current provider transport | `GenAIClient` (`ai/client/core.py`) executes a single chat-completion request; `ai/providers/` supplies OpenAI/Azure/fake providers | Existing parallel provider/client stack is migration evidence, not the required target |
| Required target client | `ai/ai_clients/llm_core/LLMInterfaceCore` plus its provider adapters and tool contracts | Target client package per the [agentic-state framework](../../../../ai-engineering/runtime/agentic-state-framework.md); focused corrections are in scope if its contracts conflict with the accepted docs |
| Executable tools | `ToolExecutor` maps tool names to Python callables and normalizes outputs to `ToolResult`; runtime builds the mapping/toolbox | Transfer application executable definitions and DTOs to the agreed client/toolbox boundary; preserve one authoritative mapping/dispatch/loop |
| Continuation | `LLMSessionContinuation` stores transcript, pending calls, interaction data, events, and used-call count | Compare only required user-input continuation needs with the accepted history/session contracts; do not retain a duplicate session owner by default |

The source search found **no production imports of `my_digital_brain.ai.ai_clients`
outside the `ai_clients` package itself**. Thus the required package currently
exists but is not connected to the active application path. The current active
path is `AgenticStateRunner -> LLMSessionRunner -> GenAIClient` (with provider
objects composed by the app). No provider-selection decision is open: OpenAI
and Azure are the accepted initial adapter direction.

## Accepted tool-cap behavior

The target behavior is defined in the canonical
[tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md):
the required `ai_clients` layer has a configurable tool-call cap with a
configured default. Reaching it does not terminate the interaction. Calls that
cannot be executed receive synthetic outputs paired to their original
provider-issued IDs; the next provider request has no toolbox and produces the
assistant response returned to the invoker. During implementation, compare the
current session runner's round cap and repeated-call guard with this contract;
those code details are evidence, not target policy.

## Census conclusion

The accepted specs already resolve the target architecture. The rebuild must
connect states to `ai_clients`, keep the provider/tool loop in that client
layer, and make versioned Markdown the sole production prompt source selected
explicitly by prompt reference. Migrate prompt bodies only after reviewing
which current content remains functionally valid; do not copy unused templates,
compatibility exports, or the parallel session loop wholesale.
