# Product Foundation

## Vision

My Digital Brain is a private personal memory workspace. It helps its owner
capture experiences and knowledge over time, understand how they connect, and
retrieve them later through conversation and exploration.

Chat is an input and question-answering surface; the durable product is the
owner's connected, source-aware memory. Detailed node, relationship, and
evidence semantics are defined in the [network documentation](../network/README.md).

## Initial product boundary

The first product serves one private owner. Multi-tenant onboarding, team
administration, billing, and public SaaS concerns are outside the initial
product scope.

The system should work in both local-friendly and hosted deployments. The
service and deployment boundaries are described in [system
architecture](../architecture/system-architecture.md).

## Product goals

- Make capturing a memory through natural interaction low friction.
- Help the owner find useful answers and navigate to their supporting context.
- Preserve meaningful uncertainty and the subjective experience attached to
  memories, not only isolated factual statements.
- Let the owner inspect, correct, and improve stored understanding over time.

Specific user-visible capabilities and acceptance expectations are owned by
[functional requirements](functional/README.md) and [UI
requirements](ui/README.md).

## Product principles

- The owner remains the authority over personal truth.
- Preserve useful memory and its evidence; do not silently erase history.
- Represent uncertainty rather than presenting an inference as a confirmed
  fact.
- Ask for clarification when it materially improves correctness, without
  turning ordinary capture into a maintenance form.
- Keep important information explainable through its sources.
- Treat user-stated perceptions as the user's experience, not objective truth
  about another person or thing.

## Non-goals for the first version

- Perfect autonomous memory creation without user correction.
- Replacing a notes app, calendar, file manager, or CRM.
- Large-scale collaboration or public SaaS administration.
- Real-time processing of every external service.
- Deep understanding of every media type before reliable text and voice capture.
