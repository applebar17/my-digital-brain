# Census chat and clarification files

**Status: In progress**

## Principle

The HTTP/channel/session and user-question contracts are application behavior;
the current runtime result types and state IDs are replaceable internals. Each
file below must be checked for its actual caller before final disposition.

## Chat and API

| File / current role | Useful signal | Do not port | Treatment (with evidence/open point) |
| --- | --- | --- | --- |
| `src/my_digital_brain/api/routes/chat.py` | Public route shape, authentication, request/response endpoints. | Dependence on internal agentic frame DTOs at API boundary. | Retain API boundary; adapt to new app service. |
| `src/my_digital_brain/chat/__init__.py` | Current public chat symbols. | Re-export of implementation internals. | Rebuild exports after cutover. |
| `src/my_digital_brain/chat/activity.py` | Activity title/copy and variant rotation for user-facing progress. | Coupling to current `AgenticStateId`. | Preserve UX behavior; map new states explicitly. |
| `src/my_digital_brain/chat/agentic_renderer.py` | Final response, clarification, and diagnostics mapping. | Agentic-runtime result dependency as public chat response contract. | Keep chat response semantics; replace mapper input. |
| `src/my_digital_brain/chat/enums.py` | Chat channel and response-state vocabulary. | Any agentic runtime state encoded as a chat enum without a user/API need. | Inspect individually; retain stable external values. |
| `src/my_digital_brain/chat/exceptions.py` | Chat/application error categories. | Agent-runtime implementation exceptions leaking to chat. | Retain user-safe API errors; re-map runtime failures. |
| `src/my_digital_brain/chat/factory.py` | Production composition and dependencies for chat, graph, provider, history. | Direct construction of old state runner/runtime. | Retain composition root; replace agentic dependencies. |
| `src/my_digital_brain/chat/models.py` | Request/response/session/message DTOs and persistence shapes. | Internal run-result fields duplicated into outward contracts. | Strong stable-contract candidate; compare field-by-field with API/storage. |
| `src/my_digital_brain/chat/relational_store.py` | Relational persistence adapter. | Runtime-specific transcript assumptions not needed by product storage. | Retain storage responsibility; inspect schema compatibility. |
| `src/my_digital_brain/chat/runtime.py` | User message entry, persistence, clarification answer and resumption. | Agentic orchestration hidden inside the chat application service. | Preserve chat lifecycle; delegate to new orchestration boundary. |
| `src/my_digital_brain/chat/store.py` | Session/message storage protocol and in-memory implementation. | Duplicated workflow state storage if persistence already owns it. | Retain stable persistence contract after data review. |
| `src/my_digital_brain/chat/telegram.py` | Telegram channel adapter. | Coupling to runtime-specific event/result internals. | Retain channel integration; rewire at app boundary. |
| `src/my_digital_brain/chat/web.py` | Web channel adapter. | Coupling to runtime-specific event/result internals. | Retain channel integration; rewire at app boundary. |

## Clarification

| File | Useful rebuild evidence | Do not carry forward by default | Initial disposition |
| --- | --- | --- | --- |
| `src/my_digital_brain/clarification/__init__.py` | Current public clarification types. | Broad implementation exports. | Rebuild exports after ownership is established. |
| `src/my_digital_brain/clarification/contracts.py` | Question/answer, doubt, option, and outcome DTO semantics. | Duplicate internal representations of the same question lifecycle. | Preserve required user/API contracts; reassign internal DTO ownership. |
| `src/my_digital_brain/clarification/context_projection.py` | Context passed by an invoking state to the clarification capability. | Direct dependency on old reference/runtime models. | Preserve necessary context semantics; reimplement mapping. |
| `src/my_digital_brain/clarification/interaction.py` | User-interaction and pending-answer behavior. | Runtime-specific continuation protocol duplication. | Preserve the human interaction contract; integrate through one new continuation path. |
| `src/my_digital_brain/clarification/toolbox.py` | Candidate/context lookup and question-construction operations. | Untyped handlers and agentic-runtime-specific dispatch. | Retain capability behavior; register as explicit DTO-backed tools/states. |

## Completion output

Confirm callers through the route/channel composition code, identify API and
database fields that must remain stable, and link tests for final responses,
activity, clarification submission, pause, and resume. Replace the initial
dispositions above if code evidence disagrees.
