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

The context builder should ask: what information does this model call need to do this job well, and what information would distract or bias it?

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

## Practical Development Rules

- Treat schemas, tools, and prompts as one design surface.
- Keep model outputs structured when they affect memory state.
- Let the AI Manager be dynamic, but keep graph writes validated.
- Prefer context engineering over larger prompts.
- Prefer a small strong toolbox over many vague tools.
- Add deterministic code where it is clearly cheaper, faster, and more reliable.
- Add model calls where language, ambiguity, or contextual judgment matters.
- Record model inputs, outputs, prompt versions, schema versions, and tool calls when they affect persistent memory.

## Design Checklist For New AI Features

Before implementing a new AI behavior, answer:

- What is the agent trying to achieve?
- Which model is appropriate for the task difficulty?
- What structured output is expected?
- Which context is necessary?
- Which context should be excluded?
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
- Keep pending ingestion state minimal and expiring.
- Add richer deterministic handling only when real usage shows the need.
