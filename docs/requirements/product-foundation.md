# Product Foundation

## Vision

My Digital Brain is a personal memory system that turns conversations, notes, media, and external signals into a navigable knowledge graph. It should help the user remember what happened, who was involved, where it happened, why it mattered, how it felt, and how memories connect over time.

The system is not only a chatbot. The chatbot is an input and interrogation layer over a durable graph of personal knowledge.

The first product target is one private user: the owner of the brain. Public-product concerns such as multi-tenant onboarding, billing, team administration, and broad user support are deferred until the personal system proves useful.

## Primary Output

The primary output is a graph database containing:

- Entities: people, events, places, organizations, objects, media items, topics, tasks, documents, and other memory-relevant concepts.
- Relationships: typed edges between entities, with direction, confidence, timestamps, and provenance.
- Evidence: source messages, uploaded media, transcripts, metadata, user confirmations, and model extraction traces.
- Embeddings: semantic representations for entities, relationships, source chunks, and graph neighborhoods.
- Personal profile memory: durable traits, preferences, communication style, recurring goals, and other stable context about the user that can configure future LLM behavior.
- Affective memory: perceptions, emotional summaries, relationship contexts, original user wording, and emotional traits attached to memories.

## Goals

- Capture memories from natural conversation.
- Ask clarification questions during ingestion when important information is missing or ambiguous.
- Prevent duplicate graph pollution through strong identity resolution and entity unification.
- Support ambiguous real-world cases such as homonymous people, incomplete places, approximate dates, and uncertain event boundaries.
- Allow natural language interrogation of the graph.
- Allow structured querying for power users and diagnostics.
- Visualize relevant subgraphs in a dedicated frontend.
- Keep provenance and confidence visible enough to audit how a fact entered the brain.
- Preserve the emotional and subjective shape of memories, not only their factual skeleton.
- Store user-stated perceptions as user experience, not as objective truth about other people or entities.
- Capture stable user traits and preferences separately from ordinary episodic memories.
- Support voice-message ingestion early, because spoken memory capture should be low friction.
- Prepare for future media ingestion, including images, documents, links, and richer audio processing.
- Run in local-friendly and cloud-friendly deployment modes.

## Non-Goals For The First Version

- Perfect autonomous memory creation without user correction.
- Full replacement for a notes app, calendar, file manager, or CRM.
- Large-scale multi-user collaboration.
- Public SaaS features such as billing, tenant administration, and generic onboarding.
- Realtime processing of every external service from the beginning.
- Complex media understanding before the text and voice-message ingestion loops are reliable.

## Product Principles

- The user remains the authority over personal truth.
- Personal-first usefulness is more important than public-product polish in the first version.
- The system should preserve memories by default rather than aggressively pruning them.
- A memory's emotional description can be as important as its factual links.
- The graph should represent uncertainty instead of hiding it.
- Clarification should be targeted, conversational, and useful, not a long form disguised as chat.
- Every important fact should be explainable through its sources.
- The system should improve from corrections and repeated references.
- The frontend should help navigation and inspection, not only display generated summaries.

## Key Risks

- Bad entity resolution can corrupt the graph faster than later cleanup can fix it.
- Over-eager ingestion can store false or private information without enough review.
- Under-eager ingestion can lose memories, which conflicts with the main product purpose.
- Clarification fatigue can make the user stop capturing memories if every ingestion feels like maintenance.
- Natural language answers can overstate confidence if graph evidence is weak.
- Affective extraction can over-interpret the user's emotions if user-stated and LLM-inferred perceptions are not clearly separated.
- Media ingestion can become expensive and noisy without clear source modeling.
- A graph schema that is too rigid will block organic memory capture; one that is too loose will be hard to query.
- Arbitrary metadata can become unsearchable noise if it is not constrained, indexed, and linked to evidence.
