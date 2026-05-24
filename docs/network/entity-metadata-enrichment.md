# Entity Metadata And Enrichment

## Purpose

Entities need more than names and relationships. Additional metadata can unlock useful future workflows such as retrieving contact details, opening a place in a map application, syncing with contacts, or enriching a memory with external identifiers.

The design challenge is deciding what to store, what to compute at runtime, and what should become first-class graph structure.

## Metadata Categories

### Core Fields

Fields that are important for identity, filtering, display, or retrieval should be typed properties.

Examples:

- `Person.display_name`
- `Place.city`
- `Event.started_at`
- `Organization.domain`

### Structured Extensions

Fields that are important but not universal should use structured extension objects or dedicated nodes.

Examples:

- Contact details.
- External provider references.
- Social profiles.
- Address candidates.
- Place provider IDs.
- User-specific labels.

### Flexible Metadata

Flexible `metadata` is appropriate for optional, experimental, source-specific, or display-oriented information.

Examples:

- Temporary enrichment scores.
- UI display hints.
- Source-specific payload fragments.
- Experimental classifiers.

Metadata should be promoted into typed schema when it becomes frequently queried, used for entity resolution, or exposed as product behavior.

## Contact Details

Phone numbers and email addresses are valuable but sensitive and mutable. They should not be stored as arbitrary metadata once the system starts using them for retrieval or integrations.

Recommended model:

- Store contact details as `ContactPoint` nodes or structured contact objects.
- Link them to people or organizations with `HAS_CONTACT_POINT`.
- Track source evidence.
- Track validity over time.
- Mark primary values explicitly.
- Preserve old values instead of overwriting when history matters.

Example use cases:

- "What is Luca's latest phone number?"
- "Do I have an email for Giulia?"
- "Open Marco's contact details."
- "Which people from university do I have no contact info for?"

## Place Enrichment

Places can be enriched from external map providers or local geocoding services.

Possible enrichment outputs:

- Normalized address.
- Latitude and longitude.
- Provider place ID.
- Provider URL.
- Opening hours.
- Website.
- Phone number.
- Place category.

The system should distinguish between:

- User-provided place facts.
- Provider-enriched facts.
- Runtime lookup results.
- Cached enrichment data.

Provider terms, privacy constraints, and freshness requirements must be checked before storing or redisplaying third-party enrichment data.

## Runtime Lookup Versus Stored Enrichment

Not every enrichment result should be stored.

Store when:

- The value is stable and useful for future retrieval.
- The user explicitly confirms it.
- It improves entity resolution.
- It is needed offline.
- Repeated lookups would be expensive or unreliable.

Lookup at runtime when:

- The value changes frequently.
- The provider result is only needed for one answer.
- The data has licensing or retention constraints.
- Storing it would expose unnecessary private context.

Cache with expiration when:

- The value is useful but freshness matters.
- The provider allows caching.
- The system needs performance without treating the value as canonical memory.

## Enrichment Provenance

Every enriched value should track:

- Provider or tool name.
- Retrieval timestamp.
- Input used for lookup.
- Confidence.
- Whether the user confirmed it.
- Expiration or refresh policy.
- Source or evidence reference.

This prevents external tool output from being confused with user memory.

## Weak Points To Guard Against

- Metadata sprawl: too many one-off keys make the graph hard to query.
- Stale contact details: old phone numbers and emails can become harmful if returned as current.
- Provider lock-in: storing only provider-specific fields can make migration harder.
- Privacy leakage: enriching personal contacts or places may reveal sensitive context to external services.
- False precision: a map provider match may look exact while actually referring to the wrong place.

The system should treat enrichment as a proposed improvement to memory, not as automatic truth.
