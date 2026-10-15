# Census prompts and the AI-session boundary

**Status: In progress**

## Prompts

| File | Useful evidence | Do not carry forward by default | Initial disposition |
| --- | --- | --- | --- |
| `src/my_digital_brain/prompts/__init__.py` | Current prompt package surface. | Implicit registration through imports if configuration owns selection. | Rebuild only needed exports. |
| `src/my_digital_brain/prompts/models.py` | Prompt identity/version/render contract. | Untyped or duplicate prompt config. | Preserve accepted version/provenance contract; align to prompt docs. |
| `src/my_digital_brain/prompts/registry.py` | Template lookup and runtime rendering. | Registry behavior that bypasses explicit configured prompt IDs. | Verify against canonical prompt lifecycle and rewire. |
| `src/my_digital_brain/prompts/active.py` | Mapping of active prompt IDs to templates/versions. | Hidden “active” selection or state names duplicated in code. | Inventory current prompt use; rebuild config at the agreed owner. |
| `src/my_digital_brain/prompts/memory_ingestion.py` | Ingestion prompt definitions or helpers. | Duplicate prompt prose/schema guidance. | Compare with templates and ingestion prompting docs; retain only canonical prompt content. |
| `src/my_digital_brain/prompts/clarification_policy.py` | Clarification instruction policy. | Prompt-only repair of missing tool/continuation mechanics. | Keep accepted human-question behavior; assign to one versioned prompt source. |
| `src/my_digital_brain/prompts/templates/**` | Versioned system prompt content. | Unused/stale templates or duplicated prompt fragments. | Map each to actual call sites; retain only active/reapproved prompt versions. |

## Active AI-session/provider boundary

| File/group | Useful evidence | What remains undecided | Initial disposition |
| --- | --- | --- | --- |
| `src/my_digital_brain/ai/session/contracts.py` | Current session request/result/tool-call/tool mapping DTOs. | Whether these contracts are used or replaced by the user's `ai_clients` package. | Compare to reference package contracts; no assumed port. |
| `src/my_digital_brain/ai/session/runner.py` | Current tool-call iteration and continuation behavior. | Whether new states call this loop or the selected AI client directly. | Inspect correctness and caller boundary; candidate dependency, not assumed target. |
| `src/my_digital_brain/ai/session/tool_executor.py` | Current backend mapping and tool result/error execution. | Whether it duplicates the desired `llm_core` mapping protocol. | Compare behavior and DTOs directly to reference package. |
| `src/my_digital_brain/ai/session/continuation.py` | Session continuation serialization. | Persistence owner and whether state history/session owns continuation. | Inspect data lifecycle; avoid duplicate history/continuation managers. |
| `src/my_digital_brain/ai/session/__init__.py` | Public session API. | Which package becomes canonical. | Update after the AI-client/runtime boundary decision. |
| `src/my_digital_brain/ai/providers/`, `ai/client/`, `ai/models.py`, `ai/tools/` | Provider request/response schemas, SDK setup, tool spec and typed error/result structures. | Their retention/replacement scope relative to the user's reference package. | Census only direct dependencies and DTO mismatches; decision may need user input. |

## Completion output

Produce a prompt ID → actual caller/state → version/template map and a concise
comparison of the current AI-session/tool path with the user-provided
`ai_clients` design. Do not choose a provider endpoint or port code during this
census. Surface any decision needed before implementation-wave planning.
