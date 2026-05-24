# Graph Model

## Modeling Principles

- Model memories as connected facts, not isolated notes.
- Keep evidence separate from claims.
- Represent uncertainty explicitly.
- Prefer stable entity identity over perfect labels.
- Allow multiple names, aliases, and descriptions for the same entity.
- Treat time and place as first-class dimensions.
- Allow extensible metadata, but keep important queryable facts in typed fields or relationships.

## Core Node Types

### Person

A human known, mentioned, or inferred by the user.

Useful properties:

- `display_name`
- `aliases`
- `description`
- `metadata`
- `known_since`
- `confidence`
- `status`

### Event

Something that happened or is expected to happen.

Useful properties:

- `title`
- `description`
- `metadata`
- `started_at`
- `ended_at`
- `time_precision`
- `confidence`

### Place

A physical or logical location.

Useful properties:

- `name`
- `address`
- `city`
- `region`
- `country`
- `geo`
- `metadata`
- `place_precision`

### Organization

A company, institution, group, team, community, or informal organization.

Useful properties:

- `name`
- `aliases`
- `description`
- `metadata`
- `domain`

### Object

A meaningful object in memory: a book, gift, device, car, project artifact, or personal item.

Useful properties:

- `name`
- `category`
- `description`
- `metadata`
- `owner`

### Topic

A recurring theme, interest, concept, project, or subject.

Useful properties:

- `name`
- `description`
- `aliases`
- `metadata`

### Source

A raw or processed input used as evidence.

Useful properties:

- `source_type`
- `external_id`
- `channel`
- `created_at`
- `received_at`
- `content_ref`
- `transcript_ref`
- `metadata`

### Claim

An explicit fact or inferred statement that can be supported, contradicted, or revised.

Useful properties:

- `text`
- `confidence`
- `claim_type`
- `created_at`
- `valid_from`
- `valid_to`
- `metadata`

Claims are useful when a direct relationship is too lossy or when multiple evidence sources support conflicting statements.

### ProfileMemory

A durable memory about the owner of the brain that can help configure future LLM behavior or retrieval context.

Useful properties:

- `profile_key`
- `value`
- `category`
- `description`
- `confidence`
- `stability`
- `visibility`
- `metadata`

Examples:

- The user prefers concise technical explanations.
- The user tends to think in graph models.
- The user is building this project for personal use first.
- The user dislikes unnecessary product polish before the core system works.

Profile memory should not be silently treated as permanent truth. It should retain evidence, confidence, and correction history.

## Core Relationship Types

- `PARTICIPATED_IN`: Person to Event.
- `HAPPENED_AT`: Event to Place.
- `MENTIONED_IN`: Entity to Source.
- `SUPPORTED_BY`: Claim or relationship to Source.
- `RELATED_TO`: Generic low-confidence or weakly typed relation.
- `KNOWS`: Person to Person.
- `WORKS_AT`: Person to Organization.
- `OWNS`: Person to Object.
- `ABOUT`: Source or Claim to Topic.
- `LOCATED_IN`: Place to Place.
- `ALIAS_OF`: Alias node or label to Entity, if aliases become nodes.
- `SAME_AS`: Entity to Entity during merge staging or external identity mapping.
- `CONTRADICTS`: Claim to Claim.
- `DERIVED_FROM`: Entity, relationship, or claim to Source or extraction run.
- `DESCRIBES_USER`: ProfileMemory to Person, where the person is the owner of the brain.
- `CONFIGURES`: ProfileMemory to prompt, agent, or retrieval policy if configuration is represented in the graph.
- `HAS_CONTACT_POINT`: Person or Organization to ContactPoint.
- `HAS_EXTERNAL_REFERENCE`: Entity to ExternalReference.

## Provenance Model

Each graph write should preserve:

- Source identifier.
- Extraction run identifier.
- LLM model and prompt version when applicable.
- Confidence score.
- Whether the fact was user-confirmed.
- Timestamp of creation and last update.

Relationships may need their own provenance, not only nodes. For example, two people can both exist confidently while the relationship between them remains uncertain.

## Descriptions And Extensible Metadata

Every major entity should support:

- A human-readable `description`.
- Stable typed fields used for filtering and querying.
- A flexible `metadata` object for additional variable information.
- Provenance for metadata when the information is important.

The `metadata` object is useful for information that is real but not yet important enough to promote into the core schema. Examples include personal labels, source-specific attributes, external IDs, temporary analysis scores, display hints, and domain-specific details.

Metadata should not become the primary modeling strategy. If a metadata key becomes frequently queried, used in resolution, or important to the product behavior, it should be promoted to a typed property, relationship, or claim.

Sensitive, mutable, or integration-relevant details should usually be promoted early. Examples include phone numbers, email addresses, physical addresses, external profile URLs, and provider place IDs. These values need provenance, validity, privacy handling, and conflict resolution.

Recommended metadata shape:

```json
{
  "schema_version": "1",
  "attributes": {
    "custom_key": "custom value"
  },
  "source_refs": ["source-id"],
  "notes": "Optional short note about why this metadata exists."
}
```

## Contact Details And External References

Contact details can start as properties for a private MVP, but the better long-term model is a dedicated contact or external-reference structure.

Possible node types:

- `ContactPoint`: phone number, email address, website, social handle, or messaging account.
- `ExternalReference`: provider-specific identifier or URL, such as a maps link, contact-app ID, calendar ID, or social profile.

Possible relationships:

- `HAS_CONTACT_POINT`: Person or Organization to ContactPoint.
- `HAS_EXTERNAL_REFERENCE`: Entity to ExternalReference.
- `PRIMARY_CONTACT_FOR`: ContactPoint to Entity when one value is preferred.

Useful `ContactPoint` properties:

- `kind`: phone, email, website, social, messaging.
- `value`
- `normalized_value`
- `label`: work, personal, mobile, home, unknown.
- `valid_from`
- `valid_to`
- `confidence`
- `is_primary`
- `privacy_level`
- `metadata`

Useful `ExternalReference` properties:

- `provider`
- `external_id`
- `url`
- `label`
- `retrieved_at`
- `expires_at`
- `confidence`
- `metadata`

This keeps future integrations possible, such as retrieving a person's latest contact details from chat or syncing with a mobile contacts application, without treating contact data as unstructured notes.

## Identity Resolution

Candidate entities should be resolved using:

- Exact identifiers from external systems.
- Normalized names and aliases.
- Embedding similarity.
- Shared graph context.
- Location and time clues.
- Source history.
- User-specific vocabulary.
- LLM-assisted comparison.
- User clarification for close matches.

Resolution outcomes:

- Create a new entity.
- Link to an existing entity.
- Merge with an existing entity.
- Keep as unresolved pending entity.
- Ask the user for clarification.
- Reject as too uncertain.

## Handling Ambiguity

Ambiguity should not be flattened too early.

Examples:

- `Marco` may match multiple people.
- `Italy` may be too broad for an event location.
- `last summer` may need a date range with low precision.
- `the dinner` may refer to a previous event.
- `my office` may mean different places over time.

The graph should support precision metadata for dates and places, unresolved candidates, and clarification tasks.

## Embeddings

Embeddings can be attached to:

- Source chunks.
- Entity descriptions.
- Event summaries.
- Claims.
- Relationship descriptions.
- Graph neighborhoods.

Embeddings should supplement graph structure, not replace it. A semantic match should usually be followed by graph expansion and evidence inspection.
