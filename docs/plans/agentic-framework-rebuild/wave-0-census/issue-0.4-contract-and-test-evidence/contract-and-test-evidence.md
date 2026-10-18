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
| `tests/test_ai_session.py` | Provider-neutral tool loop, call-ID pairing, failures, pending continuation, and repair turns. |
| `tests/test_agentic_query_foundation.py`, `tests/test_agentic_risk_foundation.py` | Retrieval, read-only state permissions, contradiction, profile, and maintenance contracts. |
| `tests/test_graph_service.py`, `tests/test_graph_api.py` | Graph service behavior and graph API DTO/payload expectations. |

The tests describe current expectations, not automatic approval of every
assertion as a target requirement. For each test, identify the user-visible or
backend contract it protects; mark implementation-only assertions for rewrite
or removal once the replacement behavior is specified.

## Behavior evidence map

The tables classify the **behavior under test**, not the test file or current
implementation as a whole. A test can contain both a useful contract assertion
and assertions tied to an implementation that is being retired.

### Provider tool loop, call correlation, and state outcomes

| Behavior/evidence | Owning code or DTO boundary | Tests and what they establish | Classification | Census finding |
| --- | --- | --- | --- | --- |
| A provider tool call receives one output correlated to the provider-issued call ID; a nested agent's result returns to its invoker as tool output before the invoker completes. | `ai/session/contracts.py`, `ai/session/runner.py`, `agentic/runtime_state.py`; canonical `ai_clients` target | `test_ai_session.py::test_tools_and_structured_terminal_output_share_one_session`, `test_replayed_provider_tool_call_id_reuses_the_persisted_output`, `test_nested_agent_error_returns_to_the_invoking_agent_for_a_final_response`; `test_agentic_runtime.py::test_resumed_child_report_reaches_parent_invoker_tool_output`, `test_child_reuses_provider_parent_tool_call_id`, `test_internal_child_does_not_invent_provider_tool_call_id` | Backend contract | Preserve provider ID pairing and child-result return semantics in `ai_clients`, including when a child agent is plugged as a tool. Current `LLMSessionRunner` is not the target owner. |
| Tool failures return readable error information to the invoking model, which can continue and produce the terminal assistant response. | `ai/session/tool_executor.py`, session transcript/result DTOs, agentic tool binding | `test_tool_errors_are_returned_in_the_transcript`, `test_nested_agent_error_returns_to_the_invoking_agent_for_a_final_response`, `test_agentic_runtime.py::test_missing_graph_dependency_produces_tool_error_without_crashing`, `test_recovered_tool_attempt_does_not_fail_the_completed_state` | Backend contract; final assistant reply is observable behavior | Keep the error-in-transcript/re-enter-caller invariant. Rewrite tests around the canonical client/tool DTOs; do not preserve duplicate error conversion or session result classes. |
| A user-facing answer is a terminal assistant response, not a raw tool result; recovered tool attempts do not force a failed terminal state. | `LLMSessionResult`, `AgenticStateRunResult`, `chat/agentic_renderer.py` | `test_plain_text_session_completes_with_one_transcript`, `test_intermediate_agent_tool_result_returns_to_the_invoker_before_its_final_reply`, `test_agentic_runtime.py::test_conversation_entry_without_tool_call_returns_terminal_assistant_response`, `test_recovered_tool_attempt_does_not_fail_the_completed_state` | Observable behavior | Preserve final-message ownership and caller resumption; replace the current result plumbing. |
| Calls beyond the configured tool-call cap receive matched synthetic outputs; the next request has no tools and the provider supplies the final assistant response. | Accepted `ai_clients` tool-call cap in [tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md) | `test_ai_session.py::test_tool_batch_is_not_split_when_it_exceeds_cap` currently configures cap 1, executes both calls in a two-call batch, and only removes tools on the following request | Backend contract with a direct test/spec conflict | Current test expectation conflicts with the accepted cap behavior. Rewrite the test for the agreed synthetic-output behavior; do not carry forward “execute the whole over-cap batch.” |
| A user-interaction tool may pause the state and resume from its saved transcript with all remaining provider calls correctly paired. | `LLMSessionContinuation`, `AgenticFrame`, chat persistence/resume | `test_pending_tool_can_resume_from_the_same_transcript`, `test_multiple_pending_tools_keep_chat_completion_transcript_valid`, `test_pending_batch_preserves_remaining_calls_until_resume`, `test_agentic_runtime.py::test_parent_resume_does_not_repeat_its_input_tool_result_in_message_delta` | Backend contract and observable continuation behavior | Keep pause/resume meaning and transcript validity; redesign the persisted continuation representation according to `AgenticHistorySession` and the client protocol. |
| Structured output is validated and a recoverable validation error can be sent back for another model attempt. | `LLMSessionRequest.output_schema`/`output_validator`, state structured-output entrypoint | `test_invalid_structured_output_gets_a_same_history_repair_turn`, `test_invalid_structured_output_can_use_two_repair_turns`, `test_semantic_output_validation_is_recoverable_in_the_same_history`, `test_agentic_runtime.py::test_structured_state_repairs_validation_error_once` | Backend contract | Preserve DTO parsing and model-repair feedback where configured; the exact repair counter and current session outcome type are implementation details to align with the canonical client contract. |

### State invocation and history ownership

| Behavior/evidence | Owning code or DTO boundary | Tests and what they establish | Classification | Census finding |
| --- | --- | --- | --- | --- |
| A state receives purpose-specific context and a bounded toolbox; state/tool permissions are explicit. | `AgenticStateConfig`, `AgenticStateInvocation`, tool registry; target `BaseAgenticState` and typed toolbox | `test_agentic_foundation.py::test_default_state_configs_lock_wave1_toolboxes`, `test_agentic_tool_bindings.py::test_registry_validates_default_state_configs_and_reasoning_planning_states`, `test_state_toolboxes_expose_only_allowed_tools_and_no_forbidden_tools`, `test_agentic_query_foundation.py::test_memory_query_state_config_is_registered_with_read_only_tools` | Backend contract | Keep explicit purpose/tool access constraints. State IDs, registry details, and current config layout are internal and will be redefined from the accepted state framework. |
| Conversation context supplied to a model excludes channel/session metadata that is only for backend operation; child context is appropriately restricted. | `ConversationContext`, `AgenticHistoryService` | `test_agentic_history.py::test_history_service_builds_internal_conversation_and_prompt_safe_payload`, `test_history_service_child_projection_removes_channel_metadata`, `test_agentic_foundation.py::test_conversation_context_excludes_backend_channel_metadata_from_model_payload` | Backend contract/privacy boundary | Preserve purposeful context projection and prevent backend metadata leakage. Exact current `model_payload_for_state` shape is implementation detail. |
| State-local history is derived from caller/master context; only selected user-visible interactions are promoted, without duplicate or internal tool chatter leaking into master history. | `AgenticHistoryService`, chat history records | `test_history_service_promotes_selected_messages_to_master_history`, `test_history_service_promotes_clarification_question_without_options`, `test_history_service_promotes_completed_clarification_once_and_normalizes_audio`, `test_history_service_appends_source_once_to_master_history`, `test_history_service_appends_transient_message_without_mutating_conversation` | Backend contract; visible history content is observable behavior | Preserve centralized history ownership, explicit promotion, and no mutation of caller-owned history. Replace the current service and policy implementation with the accepted `AgenticHistorySession` contract. |
| History projection preserves provider transcript roles/tool outputs when an internal state requires them and applies bounded/compacted context. | `AgenticHistoryService`, `ChatMessage` | `test_history_service_renders_role_preserved_messages_and_tool_outputs`, `test_history_service_compacts_tool_events_for_planning_checkpoint_context`, plus the max-history assertion in `test_history_service_builds_internal_conversation_and_prompt_safe_payload` | Backend contract | Preserve valid transcript structure and deliberate context restriction. The current summary format, projection enum, and exact message cap are implementation details unless separately accepted by the history specification. |

### Chat response, activity, and clarification interaction

| Behavior/evidence | Owning code or DTO boundary | Tests and what they establish | Classification | Census finding |
| --- | --- | --- | --- | --- |
| The chat response carries assistant-facing primary text and structured sidecars; completed results do not republish an old clarification packet. | `ChatResponse`, `chat/agentic_renderer.py` | `test_chat_runtime.py::test_chat_response_uses_primary_text_with_structured_sidecars`, `test_chat_agentic_renderer.py::test_completed_result_does_not_republish_historical_clarification_packet` | Observable behavior/API contract | Preserve the stable chat response semantics, not the old `AgenticRunResult` dependency. Add target-runtime coverage ensuring tool output and diagnostic data cannot be selected as `primary_text`. |
| Chat persists a normal assistant completion and exposes the same message in session history. | `ChatRuntime`, chat message/session DTOs and store | `test_agentic_runtime_mode_returns_direct_assistant_response_and_persists_it`, `test_chat_api_create_list_update_and_post_to_selected_session` | Observable behavior/API contract | Preserve the HTTP/session lifecycle and final assistant message. Current `runtime_mode`/`visited_states` metadata is internal unless a consumer is confirmed. |
| A clarification answer is validated, associated with its question/option, added as hidden continuation context, and resumes the paused caller rather than restarting ingestion. Partial answers remain pending until all packet questions are answered. | Clarification DTOs/interaction service, chat answer route and persisted paused state | `test_clarification_answer_endpoint_validates_and_resumes_agentic_frame`, `test_clarification_answer_endpoint_accumulates_multi_question_progress_before_resuming`, `test_terminal_answer_resumes_the_paused_session_without_rerunning_pipeline`, `test_clarification_answer_endpoint_rejects_unknown_option_id` | Observable interaction behavior and backend contract | Preserve answer/question association and resume-the-originating-work behavior. Replace frame persistence with the accepted history/session continuation design; do not retain ingestion-specific pending DTOs. |
| Clarification packets constrain question count, unique IDs, response mode/options, and references to supplied model-facing refs rather than graph IDs. Text/audio/custom correction and informational outcomes are represented. | `clarification/contracts.py`, validation/interaction functions | `test_packet_supports_five_parallel_questions_with_unique_associations`, `test_packet_rejects_a_sixth_question_and_duplicate_ids`, `test_question_modes_validate_options_and_confirmation_shape`, `test_answers_support_text_audio_and_custom_correction`, `test_resolution_report_accepts_informational_statuses`, `test_packet_refs_reject_graph_ids_and_unknown_context_refs` | Backend contract; question usability is user-visible behavior | Retain only constraints confirmed by [clarification requirements](../../../../requirements/functional/clarification-agent-and-ux.md). The five-question cap is an explicit current requirement in that document; current UUID/frame/tool fields are not automatically target DTO fields. |
| Clarification is a read-only specialist capability and returns a resolution report through its invoking agent/tool path. | `ClarificationHandoffRequest`, clarification toolbox, child state/tool handling | `test_clarification_agent_exposes_only_wave2_tools`, `test_lookup_registers_existing_model_ref_and_redacts_graph_id`, `test_context_and_relationship_tools_accept_refs_only`, `test_ask_clarification_hands_off_detailed_doubts`, `test_resumed_child_report_reaches_parent_invoker_tool_output` | Backend contract | Keep read-only lookup/question scope and return-to-invoker semantics. The current toolbox registration and `AgenticFrame` handoff are internal. |
| Activity presented to a user is understandable and omits internal state/frame identifiers. | `ChatActivityEvent`, `ChatProcessSnapshot`, activity presentation map | `test_activity_contract_contains_no_internal_source_identifier`, `test_unknown_activity_uses_safe_user_facing_fallback`, `test_activity_title_is_stable_and_cycles_variants`, `test_in_memory_store_keeps_current_activity_separate_from_recent_history` | Observable UX/API behavior | Preserve plain-language progress and current-vs-recent activity distinction if the accepted chat UX continues to expose it. Current activity keys tied to old state IDs must be remapped. |

The tests above establish data contracts and deterministic resume behavior, but
do **not** establish that generated questions are consistently concise,
human-natural, and grounded in context. `test_memory_ingestion_prompt_hardening.py`
checks prompt text for required guidance; it is not a behavioral evaluation.
The clarification functional requirements own the expected question quality.

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
