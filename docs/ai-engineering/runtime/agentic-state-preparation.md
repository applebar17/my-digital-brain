# Agentic-state reasoning and planning preparation

## Purpose and status

**Binding framework specification.** An `AgenticState` may optionally prepare
its main session through a structured reasoning step, a structured planning
step, or both. These are internal LLM subcalls that improve the context or
organize intended work before the state begins its main agent/tool session.

Preparation is configurable per invocation. It is not a mandatory pipeline, a
hidden chain-of-thought recorder, a generic workflow language, or automatic
plan execution.

This specification extends the [agentic state framework](agentic-state-framework.md)
and uses shared context through [AgenticHistorySession](agentic-history-session.md).

## Core behavior

```text
state invocation
  -> state-local history is opened through AgenticHistorySession
  -> optional reasoning preparation call
  -> optional planning preparation call, with reasoning artifact when present
  -> main state context is assembled from the configured artifacts
  -> main LLM session and normal tool loop run
```

The presence of a reasoning or planning configuration is the flag that enables
the relevant step. Do not add a separate boolean flag alongside a missing or
present configuration.

The invoker resolves the preparation configuration before calling the base
state. It may do so through deterministic application logic or because another
agent selected an already registered state/configuration profile. The base state
does not infer whether preparation is needed, construct arbitrary prompts, or
allow a model to create arbitrary executable toolboxes.

## Context supplied to preparation

Every enabled preparation step receives:

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

## Preparation calls are separate local sessions

Reasoning, planning, and the main state session have separate local provider
transcripts. A preparation call is a subcall of the same state run, not a child
`AgenticState` and not an alternative agent-to-agent protocol.

```text
State run A
  reasoning transcript A:R  -> ReasoningArtifact
  planning transcript A:P   -> PlanArtifact
  main transcript A:M       -> assistant/tool-loop result
```

The preparation transcripts are ephemeral and are released after their
validated artifacts are passed to the main context. They are not promoted to
master history and do not appear in the main provider transcript. If an enabled
preparation toolbox uses a normal pausing tool, its continuation follows the
canonical runtime protocol; this specification does not create a special pause
path for preparation.

## Reasoning preparation

Reasoning preparation is an optional structured context-analysis call. It may
identify relevant impacts, inconsistencies, missing information, constraints,
gates, or considerations that improve later state behavior.

It is not tied to a provider “reasoning model.” The configured provider/model
and prompt determine the call; the result is a state-specific structured
artifact. Do not require the model to reveal hidden reasoning. Its DTO captures
only the decision-support information that the following state is allowed to
use.

The main state receives the validated artifact as internal context. A concrete
state determines its reasoning DTO because useful reasoning fields depend on
the state’s purpose.

## Planning preparation

Planning preparation is an optional structured call that organizes proposed
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

By default, reasoning and planning are one-shot structured-output calls with no
toolbox: one request produces one validated artifact.

Either configuration may explicitly supply a typed toolbox. In that case the
preparation call uses the normal canonical client tool loop within its own local
transcript, and must still end with its configured structured artifact. Tool
definitions and outputs follow the [DTO-first contract](../contracts/dto-first-contracts.md)
and [tool-calling protocol](tool-calling-protocol.md); they never leak into the
main state transcript.

## Configuration boundary

The target configuration has only the information needed to run the optional
step:

```text
ReasoningPreparationConfiguration
  - system prompt
  - structured output DTO
  - optional typed toolbox

PlanningPreparationConfiguration
  - system prompt
  - structured output DTO
  - optional typed toolbox
```

The invocation supplies the history projection and request. Concrete states
choose configuration profiles; they do not duplicate the generic subcall logic.
The exact DTO and module names are implementation work and must follow the
repository’s DTO-first standard.

## Initial shared planning artifact

The shared planning output is intentionally semantic and small. It describes
what should be achieved, not how backend functions, database writes, or tool
arguments must be invoked.

```python
class PlannedAction(BaseModel):
    action: str
    expected_outcome: str
    risks: list[str] = []
    implications: list[str] = []

class PlanArtifact(BaseModel):
    goal: str
    planned_actions: list[PlannedAction]
```

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
_run_reasoning_preparation(state_history, invocation)
_run_planning_preparation(state_history, invocation, reasoning_artifact)
_build_main_state_context(invocation, reasoning_artifact, plan_artifact)
_run_main_session(state_history, main_context)
```

Each important method documents its immediate dependencies: the history session,
configured preparation definition, canonical client, and any artifact renderer.
The implementation must keep this sequence visible rather than hiding it in
generic callback chains.

## Provider alignment

The framework remains provider-neutral. For a Responses-based adapter, each
preparation or main session has its own response lineage; the adapter preserves
the provider items required for continuation. For manual replay, this includes
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
- Default preparation is one-shot and tool-free; toolbox use is explicit.
- Preparation artifacts are typed internal context, not main-transcript chat
  messages or final user responses.
- A plan has no direct execution authority.
- Each preparation transcript is independent from the main transcript and from
  other state runs.
