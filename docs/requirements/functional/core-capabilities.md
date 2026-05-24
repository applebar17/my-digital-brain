# Functional Capabilities

## Conversational Ingestion

The user can send text or voice messages through a chat interface such as Telegram. Messages may describe memories, corrections, facts, events, people, places, or objects.

The system must:

- Receive user input from one or more ingestion channels.
- Preserve the raw input as source evidence.
- Transcribe voice messages into derived text evidence.
- Extract candidate entities and relationships.
- Extract candidate contact details, external references, and metadata patches when present.
- Extract candidate profile memories when the user reveals durable traits, preferences, or goals.
- Detect missing or ambiguous information.
- Ask focused clarification questions when needed.
- Apply user answers back to the pending ingestion.
- Write confirmed or sufficiently confident facts into the graph.
- Store uncertain facts with explicit confidence and provenance when appropriate.

## Personal Profile Memory

The system should detect stable information about the owner of the brain and store it separately from ordinary memories.

It should support:

- Personality traits.
- Communication preferences.
- Stable goals.
- Work style.
- Recurring interests.
- Privacy preferences.
- User-specific vocabulary.

Profile memory should be used to improve future LLM behavior, retrieval, and clarification decisions. It must remain inspectable and correctable by the user.

## Clarification Loop

The ingestion process must be able to pause and ask questions such as:

- Where did this happen?
- Who was involved?
- Which Marco do you mean?
- Was this in Rome, Milan, or somewhere else in Italy?
- Did this event happen today, yesterday, or on another date?
- Is this a new person or someone already in the graph?

Clarification should be triggered by:

- Missing required fields for an entity or relationship.
- Multiple plausible matches during entity resolution.
- Low confidence extraction.
- Conflicting facts already present in the graph.
- User-configured policies for sensitive facts.
- Contact details, addresses, or external enrichment results would be stored or changed.
- Meaningful contradictions that would affect future answers.

Clarification should stay lightweight. The system should preserve low-precision or uncertain memories when asking would create unnecessary friction.

## Entity Resolution And Unification

The system must identify when new information refers to an existing entity.

It must handle:

- Homonymous people.
- Nicknames and aliases.
- Incomplete locations.
- Repeated events described with different wording.
- Objects with similar names.
- Organizations that changed name or have abbreviations.
- Conflicting or evolving facts.

Resolution should use a combination of deterministic rules, embeddings, graph context, source metadata, LLM reasoning, and user confirmation.

## Entity Metadata And Enrichment

The system should support useful structured metadata on entities without turning metadata into an uncontrolled dumping ground.

It should support:

- Contact details for people and organizations.
- External references such as provider IDs, map links, profile URLs, and contact-app IDs.
- Enriched place data such as normalized addresses and coordinates.
- Runtime lookup for information that should not be stored permanently.
- Cached enrichment with expiration when freshness matters.
- Provenance and confirmation status for stored enrichment.

Contact details and enriched external data should be inspectable, correctable, and removable.

## Interrogation

The user can ask natural language questions such as:

- Who did I meet in Milan last spring?
- What do I know about Luca?
- Show me memories related to my trip to Japan.
- What places are connected to Capco events?
- Which people have I mentioned together most often?
- What is the latest phone number I have for Luca?
- Open the map link for the restaurant I went to with Giulia.
- Show me a timeline of my memories from last summer.
- Show me memories around Milan on a map.

The system must:

- Retrieve relevant graph entities, relationships, and source evidence.
- Use semantic search and graph traversal together.
- Generate grounded answers.
- Expose uncertainty and provenance.
- Offer follow-up navigation paths.

## Structured Querying

The system should support structured queries for advanced inspection. The exact language is open, but candidates include Cypher, Gremlin, SQL over graph tables, or a query builder that compiles to the selected backend.

Structured queries should support:

- Entity lookup.
- Relationship traversal.
- Filtering by time, place, type, confidence, and source.
- Neighborhood extraction for visualization.
- Debugging of ingestion and unification decisions.

## Visualization

The frontend should display relevant portions of the graph.

It should support:

- Entity detail views.
- Relationship lists.
- Interactive graph neighborhoods.
- Timeline view.
- Map view.
- Search and filtering.
- Source/evidence inspection.
- Confidence and ambiguity indicators.
- Manual merge, split, and correction workflows in later versions.
- Profile memory inspection and correction in later versions.

## Deployment And Access

The system should support:

- Local personal use through containers or a local runtime.
- Cloud deployment for always-on integrations.
- Local chat or frontend access when Telegram is unavailable or not desired.
- Telegram integration when public connectivity is available.
- Migration between local and cloud modes through backup and restore.

## Media And External Sources

The system should ingest voice messages early and should eventually ingest:

- Voice messages.
- Images.
- Other audio files.
- Documents.
- Links and web pages.
- Calendar entries.
- Location history or check-ins, if explicitly enabled.
- Other personal data exports.

The first version should model media as source evidence even if deep media understanding is deferred. Voice messages are the exception: they should be transcribed early because spoken memory capture is a core ingestion behavior.
