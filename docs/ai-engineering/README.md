# AI Engineering Principles

## Purpose

These principles guide how AI features should be designed and implemented in My Digital Brain. The project should stay agentic and dynamic, but graph writes, source handling, privacy, and tool execution must remain structured and guarded.

The goal is not to make every flow deterministic. The goal is to use model reasoning where it is valuable, while keeping enough structure around it to make the system reliable, debuggable, and safe.

## Core Principles

### 1. Structure Unstructured Input Explicitly

Information is extracted from unstructured text, transcripts, media-derived text, and chat history through structurization processes.

When asking a model to extract information, the request should include the expected structured output contract, preferably as a Pydantic object or equivalent schema. The model should produce structured proposals, not direct database mutations.

Examples:

- Candidate entities.
- Candidate relationships.
- Candidate claims.
- Candidate metadata patches.
- Candidate clarification questions.
- Candidate tool calls.

### 2. Schemas And Tool Descriptions Are Prompt Surface

Pydantic field descriptions, JSON schema descriptions, tool names, tool descriptions, enum values, and parameter descriptions are part of the prompt.

They must be:

- Clear.
- Unambiguous.
- Domain-specific.
- Short enough to avoid noise.
- Explicit about constraints and expected behavior.

Bad schema descriptions can confuse the model as much as bad prompt text.

### 3. Prefer Modular Model Calls Over Heavy Requests

Large overloaded prompts increase hallucination risk and make failures harder to debug.

Prefer modular steps when useful:

- Intent detection.
- Context building.
- Entity extraction.
- Relationship extraction.
- Entity resolution support.
- Contradiction detection.
- Answer generation.
- Tool selection.

Contradiction handling should prefer a specialized judge call when there is meaningful doubt. The memory-writing agent should not rely on brittle deterministic contradiction rules; it should inspect retrieved graph context and invoke the judge when it can explain the suspected conflict.

Modularity should reduce cognitive load for the model, but it should not add unnecessary latency or cost for trivial tasks.

### 4. Use AI Dynamically Where It Adds Value

LLM-based systems should not be designed like purely deterministic software. A good agent can use context, tools, and reasoning to handle cases that would otherwise require many brittle branches.

For each problem, decide whether it is better solved by:

- Deterministic code.
- A constrained model call.
- An agent with tools.
- A hybrid approach.

The tradeoff is cost, latency, reliability, and implementation complexity. If a deterministic solution is simple and reliable, use it. If the problem is contextual, ambiguous, or language-heavy, use the model.

### 5. Context Building Is Fundamental

Every model step needs the right context for the job. Context should be intentionally built, not dumped.

Context may include:

- Current user message.
- Relevant interaction history.
- Pending ingestion state.
- Retrieved graph entities.
- Source evidence.
- User profile memory.
- Privacy and trust constraints.
- Tool results.
- Previous extraction candidates.
- Nearby graph context for proposed writes.
- Current state plus relevant history when checking for contradiction risk.

The context builder should ask: what information does this model call need to do this job well, and what information would distract or bias it?

For memory-writing calls, context should include enough nearby graph state for the agent to notice possible contradictions: similar entities, current facts, historical states, related sources, relationship contexts, perceptions, time context, and place context. This context enables agentic suspicion before a contradiction judge is invoked.

### 6. Tooling Enables Dynamic Processes

Actions, intent handling, and process management can be dynamic when the AI Manager has well-defined tools and proper context.

The model can infer which tool or pipeline is appropriate, but tools must have clear contracts.

Good tools should:

- Have narrow responsibilities.
- Use clear input schemas.
- Return structured outputs.
- Be auditable when they change state.
- Fail explicitly.
- Avoid hidden side effects.

### 7. Define Agent Behavior Before Plugging Tools

In agentic development, define the behavioral protocol of the agent before adding many tools.

The protocol should clarify:

- What the agent is responsible for.
- What it must never do.
- When it should ask the user.
- When it should call tools.
- Which tool calls require confirmation.
- How it handles uncertainty.
- How it recovers from invalid tool output.

Tools should then be added to support that behavior, not to let the agent improvise without boundaries.

For contradiction handling, the behavioral protocol is:

- Memory-writing agents may raise a contradiction doubt when retrieved context conflicts with a proposed write.
- The doubt must include a short explanation grounded in provided context.
- A contradiction judge tool reviews the doubt and may inspect more graph context through read-only tools.
- The judge returns a structured decision and recommended action.
- The judge does not mutate the graph directly.

### 8. Guardrails Protect Against Bad Loops

Agentic flows need deterministic guardrails to prevent unstable behavior.

Guardrails may include:

- Max tool-call iterations.
- Allowed tool sets per task.
- Required structured output validation.
- Confirmation before risky graph writes.
- Privacy checks before provider calls.
- Expiration for pending processes.
- Retry limits.
- Fallback behavior.
- Read-only tool scopes for judge investigation.
- Mandatory structured outputs for judge decisions.

The agent can be dynamic inside the guardrails. The guardrails prevent runaway loops, accidental writes, and confusing user experiences.

### 9. Manage Context Size Deliberately

Token budget is a product and engineering constraint.

The system should:

- Keep recent context available when relevant.
- Summarize older context.
- Retrieve only relevant graph/source evidence.
- Avoid stuffing entire histories into prompts.
- Preserve durable facts in graph/profile memory instead of relying on chat history.
- Track which summaries are model-generated and when they were generated.

Summaries should preserve decisions, unresolved questions, entity references, and important user preferences.

### 10. Route Tasks To Appropriate Models

Model choice should depend on task difficulty.

Use cheaper, faster models for:

- Simple classification.
- Format conversion.
- Basic extraction.
- Short summarization.
- Tool argument drafting with low risk.

Use stronger models for:

- Ambiguous entity resolution.
- Complex memory extraction.
- Contradiction reasoning.
- Multi-step planning.
- Sensitive or high-impact graph updates.
- Final answers requiring careful synthesis.

The AI Manager should eventually support model routing by task type, expected difficulty, privacy level, latency budget, and cost budget.

### 11. Prompt Guardrails Should Be Restrictive But Natural

Prompts should restrict hallucination and unsafe behavior without making the model rigid or unnatural.

Good guardrails:

- Tell the model what it can and cannot infer.
- Require uncertainty to be represented explicitly.
- Require evidence references when available.
- Forbid direct graph mutation outside tools.
- Encourage clarification when needed.
- Allow graceful "unknown" answers.

Overly rigid prompts can make the agent brittle. Under-specified prompts invite hallucination.

### 12. Simplify IDs In Model Context

Long opaque database IDs are bad prompt material. They increase token usage, are hard for humans to inspect, and are easy for models to copy incorrectly.

When passing graph context to a model, the context builder should map internal persistent IDs to short temporary aliases.

Example:

```text
Internal UUID 8f1f7c3a-... becomes NODE_000001.
Internal UUID 17dc7a91-... becomes CLAIM_000001.
Internal UUID 72ad38f4-... becomes SOURCE_000001.
```

The model should use the aliases in structured outputs and tool arguments. The backend must resolve aliases back to internal IDs before validation and execution.

Rules:

- Aliases are scoped to a single model context or process step.
- Aliases are not canonical IDs.
- Alias maps should be explicit in the context.
- Failed alias resolution should fail validation.
- The model should never invent aliases that were not provided.

## Practical Development Rules

- Treat schemas, tools, and prompts as one design surface.
- Keep model outputs structured when they affect memory state.
- Let the AI Manager be dynamic, but keep graph writes validated.
- Prefer context engineering over larger prompts.
- Prefer a small strong toolbox over many vague tools.
- Add deterministic code where it is clearly cheaper, faster, and more reliable.
- Add model calls where language, ambiguity, or contextual judgment matters.
- Use short LLM-facing aliases instead of raw database IDs in prompts and tool schemas.
- Record model inputs, outputs, prompt versions, schema versions, and tool calls when they affect persistent memory.

## Design Checklist For New AI Features

Before implementing a new AI behavior, answer:

- What is the agent trying to achieve?
- Which model is appropriate for the task difficulty?
- What structured output is expected?
- Which context is necessary?
- Which context should be excluded?
- Which internal IDs need LLM-facing aliases?
- Which tools are available?
- What are the deterministic guardrails?
- What happens if the model is uncertain?
- What happens if validation fails?
- What state changes must be auditable?
- What privacy or provider constraints apply?

## Relationship To The MVP

For the MVP, these principles imply:

- Use Pydantic objects for extraction and tool contracts.
- Keep the AI Manager responsible for dynamic conversation and process control.
- Keep the Network API responsible for structured graph operations.
- Use cloud AI services initially, with provider boundaries documented.
- Support voice transcription as a first-class ingestion path.
- Use LLM-facing ID aliases for graph context and tool calls.
- Keep pending ingestion state minimal and expiring.
- Add richer deterministic handling only when real usage shows the need.
