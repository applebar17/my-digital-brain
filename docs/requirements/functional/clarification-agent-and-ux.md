# Clarification Agent And User Experience Requirements

## Status

This document is a mandatory functional specification for clarification
interactions. It defines the user-facing behavior and the session boundaries
that implementation must preserve. Technical implementation may change, but
it must not introduce a second clarification workflow, compatibility facade,
deprecated contract, or duplicated source of truth.

## Purpose

When an LLM cannot make an informed decision from the available context, it
must be able to delegate the doubts to a dedicated clarification session. The
clarification session gathers the minimum useful information from the user,
using a channel-neutral UX contract, and returns a structured resolution report
to the invoking LLM session.

The primary goal is a clear and low-friction user experience. The user must be
able to correct missing or incorrect graph context instead of being forced into
an opaque backend decision.

## Core Principles

- `ask_clarification` remains an LLM tool at the invoker boundary.
- Calling `ask_clarification` is a handoff to a new clarification-agent LLM
  session; it is no longer a deterministic question-building function.
- The clarification session inherits the master LLM history and the supplied
  doubts. It is a child interaction within the same chat, not a new chat.
- Text and audio are equivalent answer modalities. Wherever text is accepted,
  audio must also be accepted and transcribed or otherwise normalized before it
  is returned to the agent.
- Free text must be available in almost every scenario. A user must be able to
  correct a wrong lookup, interpretation, candidate list, or option set.
- The LLM decides which doubts to investigate and which question to ask. The
  backend validates contracts, manages session continuation, renders packets,
  and maps references; it does not make the semantic decision.
- Clarification result statuses guide LLM behavior but do not deterministically
  stop, reject, or branch the broader pipeline.
- The clarification agent has no graph-write capability.
- Persisted graph IDs never appear in model-facing or user-facing contracts.
- New code must have one canonical implementation and one clear ownership
  boundary. No legacy aliases, duplicate paths, or hidden fallbacks may be
  added.

## End-To-End Lifecycle

The lifecycle is a sequence of resumed API calls over an accumulating history.
It must never rerun or restart the enclosing pipeline from the beginning.

1. An invoking LLM session decides that one or more doubts require user input.
2. It calls `ask_clarification` with a detailed list of doubts and supplied
   model-facing references.
3. The backend creates or resumes a clarification-agent session with:
   - the master LLM history;
   - the invoker's doubts;
   - the relevant candidate and graph context;
   - a clarification-specific system prompt;
   - the clarification toolbox.
4. The clarification agent may query the graph and may issue one or more
   questioning tool calls, including parallel calls when questions are
   independent.
5. A questioning tool produces a channel-neutral question packet. The
   frontend, Telegram adapter, or terminal renderer presents it to the user.
6. The user answers with the available text, audio, selection, or combination
   of modalities. Text input must remain available even when suggestions or
   buttons are shown.
7. The backend normalizes the answer, appends the question and answer to the
   master LLM history, appends the tool output to the clarification session
   history, and makes the next API call with the updated history.
8. The clarification session continues until it has enough information to
   report its current understanding. It may ask more questions when necessary.
9. The clarification agent returns one structured resolution entry for every
   supplied doubt.
10. The validated resolution report becomes the tool output of the original
    invoker session. The invoker resumes with its existing transcript and
    decides whether to create, update, attach, defer, or perform another
    clarification handoff.

There is no full-pipeline rerun. A resumed call carries forward the internal
history already produced by the relevant session, including tool calls, tool
outputs, clarification answers, and model-facing context.

## History Requirements

The system maintains distinct history projections:

### Visible Chat History

This is the history displayed to the user as normal conversation. During a
long-running ingestion or agent workflow, intermediate clarification details
are not emitted as ordinary final chat messages unless the channel requires
them for interaction.

### Master LLM History

This is the shared contextual history inherited by later LLM sessions in the
same chat. For each clarification it receives only the useful conversational
exchange:

```text
assistant: Who is Amos?
user: Amos Vignaroli
```

The master history must not be polluted with raw tool schemas, packet IDs,
option IDs, provider responses, graph IDs, or the internal reasoning of the
clarification agent. The assistant question is stored without a duplicated
option listing; the structured options remain available in the active
clarification transcript and UI packet.

### Clarification-Agent Session History

This is the complete transcript for the delegated session. It may contain:

- the inherited master history;
- the original doubt packet;
- graph lookup calls and outputs;
- questioning tool calls and outputs;
- normalized user answers;
- the final structured resolution report.

The session is resumed by appending to this history and making another API
call. It is not reconstructed from the original user message.

## Invoker Handoff Contract

The invoker must provide verbose, source-grounded doubts. A doubt is a
behavioral guideline for the clarification agent, not a deterministic command
to produce a particular answer.

Each doubt must identify:

- a run-scoped `doubt_id`;
- a detailed description of the uncertainty;
- one or more model-facing refs;
- missing information, when known;
- why the uncertainty matters;
- supporting evidence refs, when available.

Example:

```json
{
  "doubts": [
    {
      "doubt_id": "DOUBT_001",
      "doubt": "Amos is mentioned only by first name and no similar person was found in the graph.",
      "refs": ["CANDIDATE_PERSON_004"],
      "missing_information": "Full name or another distinguishing detail",
      "why_blocking": "The identity is incomplete and may produce an ambiguous person node.",
      "evidence_refs": ["CANDIDATE_EVENT_001"]
    }
  ]
}
```

The handoff response may be an external-interaction continuation while the
user is answering. It must not be represented as a new semantic ingestion
decision or as a request to rerun the pipeline.

## Clarification Scenarios

The clarification agent must support these major scenarios:

| Scenario | Purpose | Default interaction |
| --- | --- | --- |
| `identity_no_match` | No relevant graph candidate exists | Text or audio answer |
| `identity_ambiguous` | Several graph candidates may match | Single selection plus custom text |
| `missing_attribute` | A required identity or object field is absent | Text or audio answer |
| `confirm_proposal` | The user must confirm a proposed fact or action | Confirmation plus custom text |
| `correct_conflict` | Existing and proposed values disagree | Selection plus custom text |
| `relationship_target` | One or more relationship endpoints are unclear | Single or multiple selection plus custom text |
| `explicit_discard` | The user has indicated that data should not be saved | Confirmation plus custom text |

Place and date disambiguation use these existing generic interaction modes for
now. They do not require dedicated place or date UI tools in this scope.

The LLM may decide that a question is unnecessary after querying the graph.
It may also ask several independent questions in parallel. The user-facing
experience must remain understandable and must preserve which answer belongs to
which question.

## UX Interaction Modes

Questioning tools and API packets must expose semantic response modes rather
than frontend-specific widgets:

- `free_text`: open text answer, with audio also accepted;
- `single_choice`: one supplied option, with text/audio correction allowed;
- `multiple_choice`: several supplied options, with text/audio correction
  allowed;
- `confirmation`: positive or negative answer, with text/audio correction
  allowed;
- `choice_or_text`: supplied options plus a custom answer;
- `text_or_audio`: explicit free-form text or audio input.

`allow_custom_answer` is `true` by default. A tool may disable it only when a
strict closed answer is functionally necessary and the contract explains why.
In normal identity, relationship, place, date, and correction scenarios,
custom text remains available as a safety valve.

The channel mappings are:

- web frontend: buttons, radio controls, checkboxes, text input, and optional
  microphone input;
- Telegram: inline buttons where useful, followed by text input for custom
  answers;
- terminal/UAT: numbered choices plus a free-text line and the same normalized
  answer contract.

Channels may render the same packet differently, but they must not change its
  semantic meaning or remove the user's ability to correct the options when
  custom input is allowed.

## Questioning Toolbox

The clarification agent receives a small, read-only toolbox.

### Graph Context Tools

- `lookup_candidates`: deterministic lookup using structured fields and
  supplied search parameters; no LLM-generated Cypher;
- `get_candidate_context`: compact details, aliases, relationships, and
  relevant evidence for supplied refs;
- `get_relationship_context`: optional compact context for ambiguous endpoints.

### UX Question Tools

- `pick_one`;
- `pick_many`;
- `confirm`;
- `ask_text`;
- `ask_text_or_audio`.

Each questioning tool creates a canonical question packet and hands control to
the channel. It does not write the graph. The tool specification must carry
the selected interaction mode, question, target refs, evidence refs, options,
summaries, and custom-answer policy.

Question options may point only to model-facing refs supplied by the backend.
The clarification agent cannot invent graph IDs or candidate refs.

For identity-disambiguation, conflict-correction, and relationship-target
questions, every selectable option must include a brief `summary` subtitle.
The subtitle is generated by the LLM from supplied context, is limited to 160
characters, and immediately explains which person, place, or relationship the
option refers to. It must not contain internal refs, persisted graph IDs, or
unsupported details. Simple confirmations may omit it when the option label is
self-explanatory.

Example:

```text
Which Amos do you mean?
- Amos Rossi - friend from elementary school
- Amos Bianchi - colleague at Rossopomodoro
```

Questions and options should be natural, concise, and written in the user's
language. When the available context cannot support a useful subtitle, the
agent should ask for free text rather than inventing a distinction.

## Clarification Agent Result

The clarification agent returns a structured report with a simple status for
each doubt. Statuses are informational guidance for the invoking LLM; they are
not deterministic backend gates.

Allowed status values are:

- `resolved`;
- `partially_resolved`;
- `unresolved`;
- `user_declined`;
- `not_needed`.

Each entry should contain, when applicable:

- the original `doubt_id`;
- the current status;
- the question and normalized user answer;
- selected model-facing refs;
- new or corrected structured values;
- user-provided evidence and provenance;
- remaining uncertainty.

An `unresolved` result does not automatically stop the invoker or ingestion
pipeline. The invoking LLM decides whether to continue, ask another question,
create a cautious candidate, update existing context, or defer based on the
full context and its instructions.

## Prompt Requirements

The clarification-agent system prompt must instruct the model to:

- address the supplied doubts rather than invent unrelated questions;
- query the graph before asking questions when more context may resolve the
  doubt;
- ask concise, user-understandable questions;
- use the most appropriate semantic interaction tool;
- provide candidate labels and summaries when graph matches exist;
- keep custom text enabled unless a strict answer is genuinely required;
- accept that text and audio are equivalent user answers;
- ask additional questions when the answer does not resolve the doubt;
- preserve user wording and distinguish explicit answers from inference;
- return a complete structured result for every doubt;
- leave semantic next-step decisions to the invoking LLM.

Invoker prompts must explain that the clarification report is evidence and
context, not an automatic graph action. After receiving it, the invoker must
apply clarified values to its own structured create/update/memory/relationship
proposal.

## Multi-Wave Integration Plan

The waves below describe the complete integration path. Each wave must leave
the existing chat, ingestion, and graph-write behavior intact outside the
clarification paths it explicitly changes. New feature modules should remain
focused and below 500 lines. No wave may add compatibility wrappers or retain a
superseded implementation beside the canonical one.

### Wave 0: Contract Boundary And Session Shape

**Goal:** Lock the handoff and continuation boundaries before changing UX or
agent behavior.

Activities:

- Define the invoker `ask_clarification` request with detailed doubts,
  model-facing refs, missing information, blocking rationale, and evidence.
- Define the clarification-agent session input and structured resolution
  report.
- Define the distinction between master LLM history and clarification-session
  history.
- Define the informational result statuses without attaching deterministic
  pipeline gates to them.
- Remove or replace any old clarification entrypoint that duplicates the
  canonical handoff contract.

Exit criteria:

- One canonical handoff contract exists.
- The invoker can pause and resume using the same accumulated transcript.
- The clarification agent has no graph-write capability in its contract.
- Contract serialization tests cover valid and invalid references.

### Wave 1: UX Interaction Contract

**Goal:** Define the user experience independently from any specific channel.

Activities:

- Add the clarification kinds for no-match identity, ambiguous identity,
  missing attributes, confirmation, correction, relationship targets, and
  explicit discard.
- Add semantic response modes for free text, single choice, multiple choice,
  confirmation, choice-or-text, and text-or-audio.
- Make text and audio equivalent answer modalities wherever text is accepted.
- Make custom answers enabled by default.
- Define option labels, compact summaries, model-facing target refs, and the
  `Other` option semantics.
- Group up to five parallel questions in one packet with independent question
  IDs and answer associations.
- Allow channels to present grouped questions sequentially without changing
  packet or question identity.
- Represent audio answers with an opaque media reference and normalized text.

Exit criteria:

- A channel-neutral packet describes every supported interaction.
- The same packet can be rendered as web controls, Telegram controls, or a
  terminal interaction.
- Users can correct supplied options through custom text in normal scenarios.
- UX contract tests cover all initial clarification kinds and response modes.

### Wave 2: Questioning Toolbox And Read-Only Context

**Goal:** Give the clarification agent the minimum capabilities required to
  investigate doubts and ask questions.

Activities:

- Implement the read-only graph tools:
  `lookup_candidates`, `get_candidate_context`, and the optional relationship
  context lookup.
- Implement semantic questioning tools:
  `pick_one`, `pick_many`, `confirm`, `ask_text`, and `ask_text_or_audio`.
- Update tool schemas to require supplied refs and structured options where
  applicable.
- Include the LLM-generated `summary` subtitle in option contracts and require
  brief summaries for identity-ambiguous, conflict-correction, and
  relationship-target choices.
- Validate that no tool request contains persisted graph IDs or invented refs.
- Ensure the questioning tools produce canonical packets rather than channel-
  specific responses.
- Resolve the final names and payload shape for selection tools.

Locked Wave 2 limits and interaction behavior:

- `lookup_candidates` accepts the candidate ref, entity type, display name,
  aliases, typed identity values, and a bounded candidate limit. The default is
  five candidates and the hard maximum is ten.
- `get_candidate_context` and `get_relationship_context` accept model-facing
  refs only and return bounded projections without persisted graph IDs.
- The five questioning tools are exposed only to `CLARIFICATION_AGENT` and
  enforce their semantic response mode in the backend mapping.
- Parallel questioning calls from one assistant turn are aggregated into one
  packet. A packet contains at most five questions.
- The LLM is instructed in both the clarification-agent prompt and questioning
  tool descriptions that five is the packet limit. The generic session tool
  budget remains 50 and is independent from the packet limit.
- If more than five questioning calls are returned in one assistant turn, the
  backend returns a retryable structured error for every call, names the full
  call set, and creates no partial packet. The model must split the questions
  in a later turn; no question is silently discarded.
- The complete assistant tool batch is executed before an external pause.
  Read-only results and all pending question calls remain in the same
  transcript. Resumption supplies one result for every pending call in the
  grouped continuation.
- A grouped continuation is the canonical session contract for external
  interactions. It contains the pending call list, interaction payload,
  transcript, tool events, and session metadata.
- Prompt examples must demonstrate human-friendly wording, meaningful option
  labels, concise subtitles, and the use of free text when context is missing.

Exit criteria:

- The clarification agent can query context without generating Cypher.
- The clarification agent can issue one or many parallel questions.
- Every question tool has one canonical backend mapping and one packet format.
- Tool contract tests reject invalid, stale, cross-run, and cross-graph refs.

### Wave 3: Master History And Clarification Retention

**Goal:** Make the shared master LLM history explicit and preserve clarification
child-session context across resumed calls.

The handoff, grouped continuation, read-only context, and questioning toolbox
are established by Waves 0–2. This wave does not add another clarification
store or provider token-compaction behavior.

Activities:

- Persist the canonical `master_llm_history` in existing chat-session metadata.
- Seed it from visible user/assistant chat messages when absent.
- Keep only ordered `{role, content}` entries in the model-facing history.
- Exclude system prompts, tool calls, tool schemas, graph lookups, packet and
  option IDs, provider diagnostics, and clarification-agent reasoning.
- Pass a snapshot of master history into each clarification child session.
- Keep the complete resumed child transcript in `AgenticFrame.messages`.
- Promote clarification question/answer pairs only after the child session
  completes, preserving question order and normalized audio text.
- Keep backend-only source and promotion keys in separate session metadata so
  repeated completion cannot duplicate exchanges.
- Continue using the existing `AgenticFrame.expires_at` retention mechanism for
  abandoned sessions without adding a dedicated cleanup subsystem.

Exit criteria:

- Master history is persisted and inherited without raw internal tool noise.
- Clarification child resumes use the saved transcript rather than rebuilding
  from the original user message.
- Completed clarification exchanges are promoted exactly once and in order.
- Pending child sessions do not modify master history.
- Existing frame parent/child linkage and expiry behavior remain unchanged.

### Wave 4: Channel And API Integration

**Goal:** Deliver the same clarification contract consistently to every input
  channel.

Activities:

- Expose the channel-neutral question packet through the application API.
- Keep the API on the canonical answer contract and return structured errors
  for invalid, stale, empty, mismatched, or unauthorized answers.
- Render one active question at a time in every channel while preserving the
  complete packet and question associations.
- In the web frontend, keep packet answers locally, support back/edit
  navigation, and submit one complete packet after the last question.
- In Telegram and terminal/UAT, submit each answer immediately and render the
  next unanswered question from the resumed response.
- Keep custom text available when the contract allows it and show option
  summaries in every channel.
- Ensure channel adapters do not reconstruct semantic decisions or duplicate
  validation logic.
- Preserve question IDs, packet IDs, and answer associations across retries or
  delayed responses.
- Defer audio/media capture, upload, storage, and transcription integration to
  a later wave; this wave only preserves the canonical transport fields.

Exit criteria:

- A user can answer every initial response mode through each supported channel
  where that input modality exists.
- Invalid, stale, empty, and mismatched answers receive structured diagnostics.
- Web users can move forward and backward through a packet without losing or
  overwriting answers.
- Telegram and terminal users receive the next question after each answer.
- Channel integration tests cover buttons, custom text, sequential packets,
  and terminal input.
- No browser media capture or transcription behavior is introduced in this
  wave.

### Wave 5: Resolution Report And Invoker Resume

**Goal:** Connect the completed clarification report back to the original LLM
  session without context loss or context pollution.

Activities:

- Return the complete validated `ClarificationResolutionReport` as the
  `ask_clarification` tool output to the invoker, including statuses,
  clarified values, selected refs, evidence, and remaining uncertainty.
- Preserve the report when a completed child resumes its parent and when
  nested parent frames are resumed; never reduce it to only a summary or
  derived answer list.
- Ensure clarified values are available to the invoker's next structured
  proposal.
- Verify that the invoker can create, update, attach, ask again, or defer based
  on the report and its own instructions.
- Persist the report in completed child-frame metadata while keeping the
  canonical transcript in `AgenticFrame.messages`.
- Preserve provenance and original user wording in the report; keep only the
  clean question/answer exchange in Wave 3 master-history promotion.
- Treat `resolved_clarifications` as derived runtime context only. The
  structured report remains the source of truth.

Exit criteria:

- Amos-like flows retain the clarified full name in the final node action.
- The invoker receives the full clarification report in the next tool message
  and does not receive stale pre-clarification candidate values as the only
  available identity data.
- Master history remains compact and ordered.
- End-to-end tests prove clarification answers and clarified structured values
  reach the next invoker turn without a pipeline restart.

### Wave 6: Prompt Policy And Agent Behavior

**Status:** implemented. A shared clarification policy is composed into every
clarification-capable agent prompt, while the conversation router and
read-only memory-answer prompt remain unchanged.

**Goal:** Make all relevant agents use the clarification capability
  consistently while leaving semantic decisions with the LLM.

Activities:

- A single reusable policy guides context inspection, detailed doubt handoffs,
  model-facing reference safety, custom answers, explicit-versus-inferred data,
  defer/ignore behavior, and continuation after reports.
- Invoker prompts consume the complete report by `doubt_id`, apply clarified
  values to structured fields, and choose the next action without restarting.
- The clarification agent receives compact examples for no-match identity,
  duplicate candidates, missing fields, correction, confirmation, and
  relationship endpoints.
- Questions remain concise, user-language, and human-friendly; duplicate
  options use brief factual subtitles and never expose internal refs.
- Resolution statuses remain informational guidance. They do not create
  deterministic pipeline stops or semantic identity decisions.

Exit criteria:

- Reasoning, planning, extraction, resolution, and clarification consumers use
  the canonical handoff behavior.
- Prompt tests verify consistent tool selection, detailed doubt construction,
  report consumption, and answer application.
- No prompt instructs the backend to make the semantic identity decision.

### Wave 7: Hardening, Observability, And Cleanup

**Status:** implemented. Backend continuation, channel contracts, structured
observability, frontend clarification components, context redaction, and
directly superseded clarification paths have been hardened.

**Goal:** Verify the complete behavior and remove directly superseded code.

Activities:

- The web client uses the active agentic frame and clarification packet as its
  only clarification lifecycle source; stale pending-process UI contracts are
  removed.
- Web clarification questions enforce response modes locally, preserve packet
  progress and edits, render option summaries, and show structured retryable or
  terminal errors inline and in the status bar.
- Web, Telegram, and terminal use the same canonical packet and answer
  contracts. Wave 7 validates text-based flows; media capture and transcription
  remain deferred.
- Structured events cover handoff, lookup, question packets, answers, report
  completion, resume, and master-history promotion without raw answers or graph
  IDs in general observability payloads.
- Model-facing context and report propagation are audited for redaction,
  complete report delivery, and absence of hidden status gates.
- Unused clarification classifier templates, duplicate mappings, and stale
  frontend pending-process paths are removed after reference verification.
- Backend tests, frontend typecheck/build, compilation, and refined-ingestion
  regression checks are required for completion.

Exit criteria:

- One clarification implementation exists across the repository.
- No legacy clarification path or compatibility alias remains.
- All supported channels produce equivalent semantic answers.
- Clarification-agent sessions resume correctly without pipeline restarts.
- The complete functional acceptance criteria in this document pass.

## Non-Goals

This requirement does not introduce:

- a new graph taxonomy for clarification records;
- a deterministic identity-resolution decision engine;
- automatic graph writes by the clarification agent;
- dedicated place or date widgets;
- a second chat conversation visible to the user;
- a full-pipeline restart or replay mechanism;
- compatibility wrappers for previous clarification contracts;
- duplicated question-building logic in channel adapters.

## Open Points

The following decisions remain open and must be resolved during implementation
without weakening the mandatory requirements above:

1. Token-threshold context compaction remains deferred; the clarification agent
   continues to inherit the existing master-history snapshot.
2. Abandoned clarification sessions continue to use the existing
   `AgenticFrame.expires_at` retention behavior; no new cleanup worker is added.

These are implementation and product-detail decisions. They must not become
new deterministic pipeline gates or create parallel clarification flows.

## Acceptance Criteria

The implementation is acceptable when:

- `ask_clarification` starts a dedicated clarification-agent session;
- the clarification session inherits the master history and supplied doubts;
- every resumed call appends to existing session history;
- no pipeline is restarted from the beginning;
- text and audio are interchangeable wherever a text answer is supported;
- custom text is enabled by default and available for correction in normal
  scenarios;
- parallel questions can be represented and answered independently;
- the clarification agent has read-only graph and questioning tools only;
- question packets are channel-neutral and renderable by web, Telegram, and
  terminal clients;
- question and answer are promoted to master history without raw tool noise;
- the invoker receives a structured report for every doubt;
- result statuses provide model guidance but never deterministically stop the
  broader pipeline;
- no persisted graph IDs, invented refs, legacy contracts, or duplicate
  clarification implementations are introduced.
