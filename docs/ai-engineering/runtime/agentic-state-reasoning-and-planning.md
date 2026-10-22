# Configurable reasoning and planning stages in agentic states

## Purpose and status

**Binding framework specification.** A concrete `AgenticState` may configure
an internal reasoning stage, planning stage, or both as part of its execution.
Each stage is a purpose-specific structured LLM call with its own instructions
and typed output. The state owns how its stage artifacts inform later stages,
the main session, or its returned result.

These are configurable state capabilities, not generic preparation callbacks,
a mandatory pipeline for every state, a hidden chain-of-thought recorder, a
workflow language, or automatic plan execution. Deterministic input/context
assembly remains an ordinary state or workflow responsibility.

This specification extends the [agentic state framework](agentic-state-framework.md)
and uses shared context through [AgenticHistorySession](agentic-history-session.md).

## Core behavior

```text
state invocation
  -> state-local history is opened through AgenticHistorySession
  -> optional reasoning stage
  -> optional planning stage, with reasoning artifact when configured
  -> state assembles context for its main session
  -> main LLM session and normal tool loop run
```

Reasoning and planning are independently configurable: a state may enable
neither, either one, or both. Presence of a stage configuration enables it;
do not add a duplicate boolean flag. Planning may run without reasoning, and
receives a reasoning artifact only when the reasoning stage ran and produced
one.

The invoker or concrete state resolves the stage configuration before the base
state runs. It may do so through deterministic application logic or because
another agent selected an already registered state/configuration profile. The
base state does not infer whether a stage is needed, construct arbitrary
prompts, or allow a model to create arbitrary executable toolboxes.

## Context supplied to each stage

Every enabled stage receives:

- the contextual history projection selected for that state from
  `AgenticHistorySession`;
- the invocation goal, pain point, or other explicit request;
- purpose-specific system instructions; and
- a dedicated Pydantic output DTO.

Planning additionally receives the validated reasoning artifact when the
reasoning step completed. The artifact is rendered as a clearly labeled context
section for the planning call; it is not silently copied as an assistant message
into another provider transcript.

“Whole history” means the full history projection allowed for this state’s
purpose. It never means raw global storage records, another state’s full
provider transcript, raw tool traces, or backend-only metadata.

## Stage calls are separate local sessions

Reasoning, planning, and the main state session have separate local provider
transcripts. A reasoning/planning stage is a purpose-specific LLM subcall in
the same state execution, not a child `AgenticState` or a generic LLM call
wrapper. It is distinct from a workflow that invokes separately addressable
states and passes DTOs between them.

```text
State run A
  reasoning transcript A:R  -> ReasoningArtifact
  planning transcript A:P   -> PlanArtifact
  main transcript A:M       -> assistant/tool-loop result
```

Stage transcripts are local to the stage and are released after its validated
artifact has been consumed by the owning state. They are not promoted to master
history or copied into the main provider transcript. If an enabled stage
toolbox invokes a UI-interaction tool, that interaction follows the same
application-owned continuation and timeout contract as any other such tool;
this specification adds no separate pause behavior.

## Reasoning stage

The reasoning stage is an optional structured context-analysis call. It may
identify relevant impacts, inconsistencies, missing information, constraints,
gates, or considerations that improve later state behavior.

It is not tied to a provider “reasoning model.” The configured provider/model
and prompt determine the call; the result is a state-specific structured
artifact. Do not require the model to reveal hidden reasoning. Its DTO captures
only the decision-support information that later stages or the main session of
the owning state are allowed to use.

The owning state decides whether and how the validated artifact informs a
later stage, its main session, or its returned result. `ReasoningArtifact` is a
reusable baseline; a concrete state may configure a purpose-specific DTO when
those fields do not express its required output.

## Planning stage

The planning stage is an optional structured call that organizes proposed
semantic actions toward the invocation goal. It receives the same allowed
history and request as reasoning, plus the reasoning artifact when present.

The plan is not a tool call, graph write, function invocation, or permission to
perform side effects. It is an internal artifact. Its frame-specific consumer is
responsible for deciding how it informs later work. The initial supported uses
are:

- include the plan as context for the main state’s agent/tool loop; or
- return the plan as the useful structured result of a planning-focused state.

Any deterministic execution of plan actions requires a separately accepted
frame-specific contract. There is no generic plan executor in this framework.

## Default one-shot behavior and optional toolboxes

By default, reasoning and planning stages are one-shot structured-output calls
with no toolbox: one request produces one validated artifact.

Either configuration may explicitly supply a typed toolbox. In that case the
stage uses the normal canonical client tool loop within its own local
transcript, and must still end with its configured structured artifact. Tool
definitions and outputs follow the [DTO-first contract](../contracts/dto-first-contracts.md)
and [tool-calling protocol](tool-calling-protocol.md); they never leak into the
main state transcript.

If a stage's tool batch needs user input, the state returns an internal
continuation cursor (`reasoning` or `planning`) together with that stage's
transcript and the canonical state transcript. Resume continues the same stage
and batch. It cannot start the next stage or main call until the batch is
complete and the stage artifact validates. Stage configuration is supplied
again by the configured state; runtime toolbox handlers are not serialized.
The cursor is not a user-facing status and does not add history messages.

When the configured sequence reaches the main call, the state passes the plan
artifact as context when planning ran; otherwise it passes the reasoning
artifact when reasoning ran. The selected artifact is added to the main system
prompt as internal context, not appended as a history message or assistant turn.

## Configuration boundary

Each stage configuration has only the information needed to run that optional
stage:

```text
ReasoningStageConfiguration
  - system prompt
  - structured output DTO
  - optional typed toolbox

PlanningStageConfiguration
  - system prompt
  - structured output DTO
  - optional typed toolbox
```

The invocation supplies the history projection and request. Concrete states
choose configuration profiles; they do not duplicate the generic subcall logic.
The shared runtime contract is `AgenticStageConfigurationDTO` containing the
stage system prompt, required response model, and optional toolbox and parallel
tool-call setting. `AgenticStateInvocationDTO` accepts optional reasoning and
planning configurations; `AgenticStateResumeDTO` receives the same
configuration again when a stage is resumed. Planning's shared result is
`PlanArtifact` with ordered `PlannedAction` values. `ReasoningArtifact` is the
shared baseline for a concise summary, impacts, inconsistencies, information
gaps, and constraints or gates. A concrete state may provide a more specific
DTO when its reasoning purpose needs a different contract.

## Initial shared planning artifact

The shared planning output is intentionally semantic and small. It describes
what should be achieved, not how backend functions, database writes, or tool
arguments must be invoked.

The DTOs are `PlanArtifact` and `PlannedAction` in
[`contracts/artifacts.py`](../../../src/product/agentic/contracts/artifacts.py).
Their Pydantic fields and descriptions are the exact structured-output
contract; the semantics below explain their intended use.

Field semantics:

- `action`: a concise semantic action, never an internal function name, raw
  database command, or invented tool invocation.
- `expected_outcome`: the observable result that indicates the action was
  useful or complete.
- `risks`: material ways the action could be unsafe, invalid, incomplete, or
  require more information. Leave empty when there is no material risk.
- `implications`: relevant effects on later actions, context, or user-facing
  behavior. Leave empty when none apply.
- `goal`: the goal addressed by the complete ordered list.
- `planned_actions`: the ordered actions. List order is the only sequencing
  mechanism in the initial shared DTO.

Dependencies, action IDs, backend operation names, raw references, execution
status, retries, and approval fields are intentionally absent. Add them only
when a specific accepted plan consumer needs them.

## Base-state method sequence

The conceptual method order in `BaseAgenticState` is:

```python
invoke(invocation)
_open_state_history(invocation)
_run_reasoning_stage(state_history, invocation)
_run_planning_stage(state_history, invocation, reasoning_artifact)
_build_main_state_context(invocation, reasoning_artifact, plan_artifact)
_run_main_session(state_history, main_context)
```

Each important method documents its immediate dependencies: the history session,
configured stage definition, canonical client, and any artifact renderer.
The implementation must keep this sequence visible rather than hiding it in
generic callback chains.

## Provider alignment

The framework remains provider-neutral. For a Responses-based adapter, each
reasoning/planning stage or main session has its own response lineage; the
adapter preserves the provider items required for continuation. For manual
replay, this includes
the original assistant/reasoning items and their provider metadata where the
provider requires them. This is adapter/client responsibility, not
`AgenticHistorySession` responsibility.

The direction follows official OpenAI guidance: Structured Outputs are the
appropriate mechanism for typed model artifacts, function calling connects the
model to application capabilities, and complex prompts should start from a
clear outcome rather than unnecessary fixed process instructions. See
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[Function Calling](https://developers.openai.com/api/docs/guides/function-calling),
and [model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5).

## Invariants

- Reasoning and planning remain optional per invocation.
- Both receive the state-appropriate contextual history and explicit request.
- Planning receives a validated reasoning artifact only when reasoning ran.
- Default reasoning/planning stages are one-shot and tool-free; toolbox use is
  explicit.
- Stage artifacts are typed state-owned context, not main-transcript chat
  messages or final user responses.
- A plan has no direct execution authority.
- Each stage transcript is independent from the main transcript and from
  other state runs.
