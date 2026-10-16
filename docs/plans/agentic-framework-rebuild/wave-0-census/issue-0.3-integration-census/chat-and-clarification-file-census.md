# Census chat and clarification files

**Status: Complete**

## Boundary observed in the current application

The chat route receives user messages and clarification answers, then delegates
to `ChatRuntime`. The runtime persists the conversation, invokes the current
`AgenticRuntime`, converts its result through the chat renderer, and persists
the resulting response/activity. Clarification answers are validated against
the active packet and resumed through the stored frame. Web and Telegram
adapters translate channel-specific input/output around that shared runtime.

This is current-code evidence, not the target design. Preserve user-visible
chat/session and question/answer behavior where required, but treat the existing
agentic frame, state IDs, and runtime-result objects as replaceable internal
contracts. These dispositions use the [shared census classification](../issue-0.1-scope-and-boundaries/define-census-scope.md).

## Chat and API

| Current file | Current role | Useful signal | Do not port | Treatment |
| --- | --- | --- | --- | --- |
| `src/my_digital_brain/api/routes/chat.py` | HTTP endpoints for chat-session lifecycle, messages, process controls, and clarification answers. | Public route behavior, authentication, request/response boundaries. | Agentic runtime DTOs at the HTTP boundary. | Keep/adapt integration boundary — preserve reviewed API behavior while adapting its application-service dependency. |
| `src/my_digital_brain/chat/__init__.py` | Exports the current chat package surface. | Which chat DTOs/services are intended for application imports. | Re-exporting implementation internals by default. | Review behavior for migration — retain only needed public exports after ownership is clear. |
| `src/my_digital_brain/chat/activity.py` | Maps current state IDs to user-facing activity titles and variants. | UX language and activity progression intent. | Coupling product copy to old agentic state identifiers. | Review behavior for migration — remap accepted activity to target workflow steps. |
| `src/my_digital_brain/chat/agentic_renderer.py` | Maps an agentic run result to chat response, clarification packet, diagnostics, and metadata. | Observable response semantics and final-message rendering. | `AgenticRunResult` as the future chat-facing contract. | Keep/adapt integration boundary — retain chat response behavior and map from target result DTOs. |
| `src/my_digital_brain/chat/enums.py` | Defines chat channels, session/response status, activity, and process vocabulary. | Values observed by API, storage, and channel consumers. | Internal workflow states exposed as public chat status without a product need. | Review behavior for migration — retain only externally required values. |
| `src/my_digital_brain/chat/exceptions.py` | Defines chat-level validation and application exceptions. | User-safe error categories and HTTP mapping. | Agentic implementation exceptions leaking across the app boundary. | Keep/adapt integration boundary — preserve application error semantics and remap runtime errors. |
| `src/my_digital_brain/chat/factory.py` | Builds provider/search/runtime collaborators and wires the chat composition root. | Application composition boundary and concrete dependencies. | Construction of the current state runner/runtime stack. | Keep/adapt integration boundary — replace agentic wiring at the composition root. |
| `src/my_digital_brain/chat/models.py` | Defines chat request/response, session/message, activity, diagnostics, snapshot, and frame DTOs. | API/storage field semantics and user-visible response shape. | Treating persisted agentic frame internals as the target state/history schema. | Review behavior for migration — crosswalk fields with API, persistence, and canonical history/clarification contracts. |
| `src/my_digital_brain/chat/relational_store.py` | Persists chat sessions, messages, frames, and activity in relational storage. | Existing durable records and storage integration boundary. | Old frame serialization as the required target runtime representation. | Keep/adapt integration boundary — retain needed persistence behavior and adapt frame/history records to the target contract. |
| `src/my_digital_brain/chat/runtime.py` | Handles chat messages, persistence, runtime invocation, clarification answer/resume, and history projection. | End-to-end chat lifecycle and human-interaction behavior. | Agentic orchestration and old runtime types embedded in the chat service. | Keep/adapt integration boundary — retain chat ownership and delegate execution to the target workflow/state layer. |
| `src/my_digital_brain/chat/store.py` | Defines chat storage operations and an in-memory implementation. | Required session/message lifecycle used by chat and tests. | Duplicate workflow/history ownership inside chat storage. | Keep/adapt integration boundary — retain application storage responsibilities, not agentic transcript policy. |
| `src/my_digital_brain/chat/telegram.py` | Adapts Telegram updates and clarification packets to/from the chat runtime. | Channel-specific input and question presentation behavior. | Coupling channel adapter to agentic frame internals. | Keep/adapt integration boundary — maintain channel behavior over the stable chat contract. |
| `src/my_digital_brain/chat/web.py` | Normalizes web-chat payloads into channel-neutral chat messages. | Frontend-to-chat request mapping. | Channel payloads carrying runtime-specific fields. | Keep/adapt integration boundary — preserve the adapter role and target request contract. |

## Clarification

| Current file | Current role | Useful signal | Do not port | Treatment |
| --- | --- | --- | --- | --- |
| `src/my_digital_brain/clarification/__init__.py` | Exports clarification DTOs and enums. | Intended public clarification contract surface. | Broad exports that expose runtime internals. | Review behavior for migration — keep only the agreed user/application contract. |
| `src/my_digital_brain/clarification/contracts.py` | Defines doubts, handoffs, question/option packets, answers, and resolution reports. | Explicit question/answer fields, stable question association, supported response modes, and ref constraints. | Treating every current internal handoff field as a frontend or target-agent contract. | Review behavior for migration — crosswalk user-facing fields to API/storage and agentic handoff docs. |
| `src/my_digital_brain/clarification/context_projection.py` | Projects graph nodes/relationships and references into clarification context. | Information needed to ask and resolve a specific human question. | Old `RefContext` and graph-ID projection implementation as target DTO ownership. | Review behavior for migration — retain required context meaning with the canonical reference projection. |
| `src/my_digital_brain/clarification/interaction.py` | Builds packets, validates answer associations/content, merges progress, and converts answers for resume. | Question-ID/option association and pause/resume interaction semantics. | A second continuation owner beside the target history/session contract. | Review behavior for migration — preserve the human interaction contract and align its state handoff to the target. |
| `src/my_digital_brain/clarification/toolbox.py` | Implements model-facing lookup/context/question operations for clarification. | Which deterministic capabilities support clarification and what question data is produced. | Current agentic dispatcher/reference coupling or ambiguous handler contracts. | Review behavior for migration — preserve accepted capabilities and bind them through explicit typed tools. |

## Evidence and follow-up

The repository contains focused evidence in `tests/test_chat_runtime.py`,
`tests/test_chat_relational_store.py`, `tests/test_chat_consumers.py`,
`tests/test_chat_agentic_renderer.py`, `tests/test_chat_activity.py`,
`tests/test_clarification_contracts.py`,
`tests/test_clarification_toolbox.py`, and
`tests/test_interactive_ingestion_clarifications.py`. Issue 0.4 will map test
cases to the exact behaviors they assert; their presence alone does not approve
the current implementation as target behavior.

The key connected path to verify against those tests is:

```text
HTTP/channel input
  -> ChatRuntime and chat persistence
  -> current AgenticRuntime invocation
  -> result/clarification rendering
  -> response persistence and channel/API output
  -> for a clarification: answer validation -> stored-frame resume
```

The file assessments follow the shared four-field template: current role,
useful signal, do not port, and one treatment classification with rationale.
Caller/test details belong here only as concise evidence; do not create a
parallel assessment template.
