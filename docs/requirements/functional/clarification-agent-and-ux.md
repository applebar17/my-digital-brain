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
- Define how parallel questions retain independent question IDs and answer
  associations.

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
- Validate that no tool request contains persisted graph IDs or invented refs.
- Ensure the questioning tools produce canonical packets rather than channel-
  specific responses.
- Resolve the final names and payload shape for selection tools.

Exit criteria:

- The clarification agent can query context without generating Cypher.
- The clarification agent can issue one or many parallel questions.
- Every question tool has one canonical backend mapping and one packet format.
- Tool contract tests reject invalid, stale, cross-run, and cross-graph refs.

### Wave 3: Clarification-Agent Session Handoff

**Goal:** Replace direct question construction with a resumable child LLM
session.

Activities:

- Make `ask_clarification` start the clarification-agent session.
- Pass master history, doubts, relevant context, system instructions, and the
  clarification toolbox into that session.
- Run the child session through the shared LLM session/tool loop.
- Pause only for external user interaction and resume by appending the answer
  and tool output to the existing session history.
- Support multiple sequential or parallel questions within one child session.
- Define persistence and expiry for abandoned clarification sessions.
- Resolve whether the child receives full master history or a bounded backend
  projection when provider context limits require one.

Exit criteria:

- No clarification path invokes the old deterministic question builder.
- User answers resume the existing child session rather than restarting an
  ingestion or rebuilding the original invoker session.
- Multiple questions can be answered independently and preserved correctly.
- Session continuation tests verify complete transcript preservation.

### Wave 4: Channel And API Integration

**Goal:** Deliver the same clarification contract consistently to every input
  channel.

Activities:

- Expose the channel-neutral question packet through the application API.
- Accept option selections, free text, audio media refs, and normalized audio
  transcriptions through one answer contract.
- Render the packet in the web frontend, Telegram, and terminal/UAT consumer.
- Keep custom text available when options are displayed.
- Ensure channel adapters do not reconstruct semantic decisions or duplicate
  validation logic.
- Preserve question IDs, packet IDs, and answer associations across retries or
  delayed responses.

Exit criteria:

- A user can answer every initial response mode through each supported channel
  where that input modality exists.
- Invalid, stale, empty, and mismatched answers receive structured diagnostics.
- Audio answers are normalized into the same agent-facing answer shape as text.
- Channel integration tests cover buttons, custom text, parallel questions, and
  terminal input.

### Wave 5: History Promotion And Invoker Resume

**Goal:** Connect the completed clarification report back to the original LLM
  session without context loss or context pollution.

Activities:

- Promote only the assistant question and user answer to master history.
- Keep question-tool details, graph lookups, and internal agent reasoning in
  the child session transcript.
- Return the structured resolution report as the `ask_clarification` tool
  output to the invoker.
- Ensure clarified values are available to the invoker's next structured
  proposal.
- Verify that the invoker can create, update, attach, ask again, or defer based
  on the report and its own instructions.
- Preserve provenance and original user wording in the report and history
  promotion.

Exit criteria:

- Amos-like flows retain the clarified full name in the final node action.
- The invoker does not receive stale pre-clarification candidate values as the
  only available identity data.
- Master history remains compact and ordered.
- End-to-end tests prove clarification answers reach the next invoker turn.

### Wave 6: Prompt Policy And Agent Behavior

**Goal:** Make all relevant agents use the clarification capability
  consistently while leaving semantic decisions with the LLM.

Activities:

- Add the shared clarification guidelines to the clarification agent.
- Update invoker prompts to provide detailed doubts and consume structured
  resolution reports.
- Teach agents to query context before asking, ask focused questions, accept
  text/audio corrections, and keep custom answers enabled.
- Teach agents to distinguish explicit answers from inference.
- Teach agents to continue intelligently after `unresolved` or
  `partially_resolved` reports rather than relying on backend gates.
- Add scenario examples for no-match identity, duplicate candidates, missing
  fields, correction, confirmation, and relationship endpoints.

Exit criteria:

- Reasoning, planning, extraction, resolution, and chat consumers use the
  canonical clarification handoff behavior.
- Prompt tests verify consistent tool selection and answer application.
- No prompt instructs the backend to make the semantic identity decision.

### Wave 7: Hardening, Observability, And Cleanup

**Goal:** Verify the complete behavior and remove directly superseded code.

Activities:

- Add end-to-end tests for all initial scenarios, channels, media modalities,
  parallel questions, continuation, and invoker resume.
- Add traces for handoff, child-session turns, graph lookups, question packets,
  user answers, history promotion, and resolution reports.
- Verify that statuses are informational and do not create hidden stops or
  automatic pipeline branches.
- Audit context sizes and remove unnecessary packet fields from model-facing
  history.
- Remove old clarification builders, duplicate mappings, obsolete tests, and
  deprecated contracts once their replacements are active.
- Run formatting, static checks, compilation, focused tests, full tests, and
  refined-ingestion UAT regression.

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

1. The exact JSON shape for media answers, including whether audio is returned
   as a media reference, a transcription, or both.
2. Whether parallel questions are always displayed together or may be
   presented sequentially by a channel while retaining their question IDs.
3. The precise graph lookup fields and limits exposed by
   `lookup_candidates` and `get_candidate_context`.
4. Whether the clarification agent receives the entire master history or a
   backend-built bounded projection when context limits require it.
5. Whether `pick_one` and `pick_many` are sufficient names for the initial UX
   toolbox or should use domain-neutral names such as `select_option`.
6. The retention and expiry policy for abandoned clarification sessions.

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
