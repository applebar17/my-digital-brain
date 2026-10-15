# Census prompts and the AI-session boundary

**Status: In progress**

The accepted prompt and AI-runtime documents define the target. This census
maps current prompt IDs/templates and provider/session callers to the required
`ai_clients` client layer. Record concrete package discrepancies and
integration needs rather than treating current session code as a competing
design.

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

| File/group | Useful evidence | Do not carry forward by default | Census outcome |
| --- | --- | --- | --- |
| `src/my_digital_brain/ai/ai_clients/` | Required target: `LLMInterfaceCore` parameter handling, adapter-based provider calls, and shared tool loop. | Existing loose or legacy implementation details that disagree with canonical DTO/protocol docs. | Confirm public call/tool contracts and record focused package corrections needed to match the docs. OpenAI/Azure are the initial adapter direction. |
| `src/my_digital_brain/ai/session/contracts.py` | Current session request/result/tool-call/mapping DTOs crossing active application callers. | Treating these as canonical if they duplicate or conflict with the required client-layer contracts. | Map actual callers and required data to target client/state DTOs; retain only app-facing needs not owned by `ai_clients`. |
| `src/my_digital_brain/ai/session/runner.py` | Current tool-call iteration, provider resumption, and terminal outcomes. | A second tool loop in agentic states or in parallel with the required client loop. | Compare behavior with canonical tool protocol; capture only integration requirements/discrepancies. |
| `src/my_digital_brain/ai/session/tool_executor.py` | Current backend tool-name-to-callable execution path and error conversion. | Duplicate mapping/dispatch/serialization ownership beside typed client/tool contracts. | Map current executable dependencies; target tool execution stays in the required client loop. |
| `src/my_digital_brain/ai/session/continuation.py` | Current persisted continuation representation and callers. | A separate continuation owner that duplicates the accepted state-history/client transcript contract. | Map storage boundary and state/client data crossing; identify any required focused adapter, not an alternate loop. |
| `src/my_digital_brain/ai/session/__init__.py` | Active public session API imports. | Keeping an obsolete session API solely for compatibility after caller migration. | Inventory imports/callers to plan a clean transition to `ai_clients`; no client-selection decision remains. |
| `src/my_digital_brain/ai/providers/`, `ai/client/`, `ai/models.py`, `ai/tools/` | Existing provider configuration, SDK use, schemas, and typed error/result dependencies. | Assuming this parallel client stack is the target or removing a capability without tracing a real consumer. | Map actual consumers and capabilities to required `ai_clients` adapters; flag concrete missing provider/service support for discussion. |

## Accepted tool-cap behavior

The target behavior is now defined in the canonical
[tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md):
the required `ai_clients` layer has a configurable tool-call cap with a
configured default. Reaching it does not terminate the interaction. Calls that
cannot be executed receive synthetic outputs paired to their original
provider-issued IDs; the next provider request has no toolbox and produces the
assistant response returned to the invoker. During the client census, record
whether the current implementation matches this contract, including how its
existing round cap and repeated-call guard affect the flow. Treat those
implementation details as evidence, not as target policy.

## Completion output

Produce a prompt ID → actual caller/state → version/template map and a concise
integration map from active callers to the required `ai_clients` interface.
Record concrete disagreements between the package and accepted DTO/provider/
tool-loop docs as focused corrections. Do not port code or select an alternate
client during this census; surface only capability/contract questions that the
docs do not already answer.
