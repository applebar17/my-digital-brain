# Clarification Agent and UX Requirements

## Purpose and scope

Clarification lets the application ask the user for information when available
context is insufficient for a reliable decision. The clarification agent asks
for the minimum useful information and returns the user's response to the
agentic state that raised the doubt.

This document owns the user-observable and clarification-specific functional
requirements. Provider transcript rules, tool-call pairing, child-session
history, and tool schema design are owned by the relevant [AI engineering
documents](../../ai-engineering/README.md).

## Required behavior

- An agentic state may delegate one or more specific doubts to a clarification
  agent through the configured clarification capability.
- The clarification agent uses the supplied doubt and available context to
  decide whether a question is needed, what to ask, and what interaction is
  appropriate. It must not invent unrelated questions.
- The interaction has three supported presentation configurations: free
  response, confirmation, and multiple choice. These configurations help the
  client render the question; they do not introduce separate semantic
  pipelines or data-type-specific question contracts.
- Questions are concise, natural, written in the user's language, and phrased
  so a person can answer without understanding graph or application internals.
- The user can answer in free text even when choices or buttons are offered.
  The user can correct a proposed option when the supplied choices do not fit.
- Where text answers are supported, audio answers must also be supported and
  normalized for the agent.
- The agent may ask multiple independent questions together; one packet contains
  no more than five questions, and each answer remains associated with its
  question and original doubt.
- Ambiguous choices include a brief, factual description that helps the user
  distinguish them. The description must not expose internal references or
  assert details unsupported by the supplied context.
- The clarification agent is read-only with respect to the memory graph. It
  returns the user's answer and its understanding to the invoking state; that
  state decides what to do next.
- An unresolved or declined answer is information for the invoking state, not a
  deterministic instruction to stop or reject the broader operation.
- The invoking state resumes the existing work with the clarification result.
  The application does not restart the whole workflow or turn the clarification
  into a separate user-visible conversation.

## Cases the clarification experience must support

| Case | User-facing purpose |
| --- | --- |
| No matching entity | Ask for a distinguishing detail or allow the user to confirm a new identity. |
| Ambiguous identity | Let the user distinguish plausible matches or provide a different answer. |
| Missing information | Ask for a useful attribute when its absence affects correctness. |
| Confirmation or correction | Let the user confirm or correct an interpretation or proposed value. |
| Conflicting information | Explain the meaningful difference and ask only when it cannot safely be retained as context. |
| Unclear relationship target | Clarify which people or objects a stated relationship connects. |
| User declines or discards | Preserve that response for the invoking state without forcing a graph action. |

Place, date, and other ambiguities use the same general interaction patterns;
they do not require a dedicated widget for every data type.

## Correlation and privacy

Each logical doubt has a unique, LLM-generated descriptive
`clarification_ref` so its result can be applied to the correct doubt when
several are active. Preserve that reference from handoff through question,
answer, result, and return to the invoker. It is internal context and must
never be shown as ordinary chat text.

Every concrete user interaction has a backend-generated `interaction_ref`. A
retry for the same doubt keeps its `clarification_ref` and receives a new
`interaction_ref`. The interaction reference is used by the API and storage
boundary and is not shown as question content.

Neither reference is the provider-generated tool-call ID. The AI client/runtime
owns provider call correlation; see the [tool-calling
protocol](../../ai-engineering/runtime/tool-calling-protocol.md). Backend IDs
must not appear in model-facing or user-facing clarification content.

## User experience

- The user sees the question and any helpful choices, not internal reasoning,
  tool output, state names, database references, or provider diagnostics.
- Choices use understandable labels and, when needed, short distinguishing
  descriptions. Free-text correction remains available by default.
- A configurable backend deadline applies to the pending interaction. A timely
  answer or timeout resolves it exactly once; timeout is returned to the agent
  as an ordinary interaction outcome rather than terminating the pipeline.
- Web, Telegram, and terminal clients may render the same interaction using
  controls appropriate to the channel, but must preserve its meaning and the
  user's ability to answer or correct it.
- A question appears as an interaction within the current chat. It must not be
  presented as though the assistant has completed the original request.
- After the answer, the assistant continues the original work and eventually
  responds based on the invoking state’s outcome.

Chat activity and visual rendering are further specified in the [chat
workspace requirements](../ui/chat-workspace.md).

## Clarification result

The result returned to the invoking state covers every supplied doubt and
communicates, as applicable:

- whether it was resolved, partly resolved, unresolved, declined, or unnecessary;
- the user's answer in a form the invoker can use;
- any selected supplied option or corrected value;
- evidence or remaining uncertainty relevant to the decision.

These outcomes guide the invoking agent but do not themselves create graph
changes, choose an identity, or stop the workflow. The invoking agent applies
the answer to its own structured proposal or decides to continue, ask again, or
defer.

## Out of scope

- A separate clarification chat or full-pipeline restart.
- Clarification-agent graph writes or deterministic semantic identity decisions.
- A dedicated interaction widget for each entity, date, or place type.
- Provider transcript formats, generic tool execution, or history persistence;
  those belong to the [AI runtime](../../ai-engineering/runtime/README.md).

## Acceptance criteria

- The agent asks focused, understandable questions grounded in the supplied
  doubt and context.
- Users can answer freely and correct unsuitable suggestions.
- Multiple questions and answers remain correctly associated with their
  originating doubts.
- The clarification result returns to the invoking state, which resumes its
  existing work and makes the semantic next-step decision.
- No internal reference, graph identifier, or tool output is rendered as the
  assistant's final answer.
- Channel-specific presentation does not change the meaning of the question or
  remove an available answer mode.

## Related technical contracts

- [Agentic state framework](../../ai-engineering/runtime/agentic-state-framework.md)
- [Agentic history session](../../ai-engineering/runtime/agentic-history-session.md)
- [Tool-calling protocol](../../ai-engineering/runtime/tool-calling-protocol.md)
- [Tool definition and toolbox](../../ai-engineering/contracts/tool-definition-and-toolbox.md)
