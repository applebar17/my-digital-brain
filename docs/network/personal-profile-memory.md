# Personal Profile Memory

## Purpose

Personal profile memory captures stable information about the owner of the digital brain. This is different from ordinary episodic memory. It helps the system understand how the user thinks, communicates, decides, and wants the assistant or agents to behave.

Profile memory is related to affective memory but not the same thing. Affective memory captures how a specific memory, person, place, or relationship feels to the user. Profile memory captures more stable traits or preferences of the user across memories.

Examples:

- Communication preferences.
- Personality traits.
- Recurring goals.
- Stable interests.
- Work style.
- Privacy preferences.
- Decision-making patterns.
- Things the user explicitly likes or dislikes.
- Recurring emotional patterns, when they are stable and not only tied to one memory.

## Why This Is Separate

If every personality observation is stored as an ordinary graph fact, it may be hard to retrieve when configuring LLM behavior. If every observation is directly inserted into prompts, the system risks overfitting, becoming stale, or treating weak inferences as hard truth.

Profile memory should sit between the graph and LLM configuration:

- Extracted from sources like other memories.
- Supported by evidence.
- Stored durably.
- Retrieved selectively.
- Used only when relevant.
- Correctable by the user.

## Profile Memory Agent

The profile memory agent watches ingestion outputs for durable self-descriptive signals.

It should detect statements such as:

- I prefer short answers.
- I like to reason from first principles.
- I am building this for myself first.
- I do not want public-product complexity yet.
- I care about auditability and correction.

It should avoid over-inference. A single emotional statement should not become a permanent trait unless the user states it clearly or it appears repeatedly.

## Storage Options

Possible storage forms:

- `ProfileMemory` nodes in the graph.
- A versioned profile file retrieved during prompt construction.
- A profile table in the operational store.
- A hybrid model where the graph stores evidence and the prompt layer consumes a generated profile summary.

Recommended starting point:

- Store profile memories as graph nodes with evidence and confidence.
- Generate a compact `profile-summary.md` or equivalent cached artifact for LLM configuration.
- Rebuild the summary from graph state when profile memories change.

## Data Model

Suggested fields:

- `profile_key`: stable identifier, such as `communication.conciseness`.
- `category`: communication, personality, goals, preferences, privacy, work_style, interests.
- `value`: the actual profile memory.
- `description`: human-readable explanation.
- `confidence`: how strongly the system believes this is true.
- `stability`: temporary, recurring, stable, or user-confirmed.
- `visibility`: whether it can be used in prompts automatically.
- `metadata`: extensible extra information.

## Use In LLM Configuration

Profile memory can be used to:

- Personalize answer style.
- Select relevant retrieval context.
- Decide how much clarification to ask.
- Tune verbosity.
- Respect privacy preferences.
- Improve entity resolution with user-specific vocabulary.

Profile memory should not override explicit user instructions in the current conversation.

Future research may explore whether stable profile memory and affective memory can support personality-trait simulation or cloning experiments. That is not an MVP behavior. The current requirement is to preserve the data foundation carefully, with provenance and user control.

## Confirmation Policy

Recommended policy:

- Explicit user statements can be stored with medium or high confidence.
- Repeated behavioral patterns can be proposed with medium confidence.
- Sensitive traits should require confirmation.
- Low-confidence inferences should remain hidden from automatic prompt configuration.
- The user should be able to inspect, edit, disable, or delete profile memories.

## Risks

- Over-personalization can make the assistant rigid.
- Weak inferences can become self-reinforcing.
- Sensitive traits can create privacy issues.
- Stale profile memories can conflict with the user's current needs.

The main risk is not storing explicit preferences. The risk is letting the system infer too much about the user and then behave as if those guesses are permanent truth.

Example:

- The user once asks for a short answer because they are in a hurry.
- The system incorrectly stores "the user always wants very short answers."
- Future answers become too terse even when the user needs depth.

The system should treat profile memory as useful context, not as permanent identity. Explicit user statements are stronger than inferred patterns, and current instructions always override profile memory.
