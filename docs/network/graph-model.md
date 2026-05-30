# Graph Model

## Modeling Principles

- Model memories as connected facts, not isolated notes.
- Keep evidence separate from claims.
- Represent uncertainty explicitly.
- Prefer stable entity identity over perfect labels.
- Allow multiple names, aliases, and descriptions for the same entity.
- Treat time and place as first-class dimensions.
- Allow extensible metadata, but keep important queryable facts in typed fields or relationships.
- Treat affective memory as first-class for every memory-bearing node and important relationship: perceptions, emotional summaries, and original user wording should be modeled explicitly when present.

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

### Perception

A subjective perception held by the user about any graph target: person, relationship context, event, place, organization, object, topic, source, claim, project, or profile-relevant memory.

Useful properties:

- `description`
- `perception_type`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `source_kind`
- `valid_from`
- `valid_to`
- `time_precision`
- `confidence`
- `privacy_level`
- `metadata`

Perceptions should not be treated as objective truth about the target. They represent the user's experienced truth and should retain provenance. This applies equally to people, places, events, objects, topics, organizations, sources, claims, and relationships.

### RelationshipContext

A memory object describing an emotionally or narratively meaningful relationship over time. It is usually between the user and another entity, but the target can be any meaningful memory anchor.

Useful properties:

- `description`
- `relationship_type`
- `status`
- `closeness`
- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `valid_from`
- `valid_to`
- `time_precision`
- `confidence`
- `privacy_level`
- `metadata`

Relationship contexts are useful when a simple edge such as `KNOWS`, `WORKED_ON`, `LIVED_IN`, or `RELATED_TO` loses the narrative and emotional history of a relationship.

Complex relationships should not be flattened into one current edge. A relationship can have many states over time, especially with ex partners, close friends, family members, organizations, projects, or places. Use a `RelationshipContext` as the stable relationship object and attach dated `RelationshipState` records when the relationship changes.

### RelationshipState

A dated state slice inside a relationship context.

Useful properties:

- `description`
- `status`
- `closeness`
- `emotional_summary`
- `emotional_valence`
- `emotion_tags`
- `original_user_words`
- `valid_from`
- `valid_to`
- `time_precision`
- `source_kind`
- `privacy_level`
- `metadata`

Relationship states can be sparse. They are meant to work like a structured diary: on date X the relationship felt close, on date Y it felt distant, on date Z it softened again.

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

### MergeRecord

An audit node for entity unification.

Merge records are created when the system decides that two or more graph nodes refer to the same real-world entity.

Useful properties:

- `merged_node_ids`
- `canonical_node_id`
- `reason`
- `merged_at`
- `performed_by`: user, system, llm_judge.
- `status`: proposed, applied, reverted.
- `metadata`

Merge records preserve why an identity decision happened, make wrong merges debuggable, and prepare the system for future split or revert flows.

### ContradictionRecord

A review node for contradictions that need more than a direct `CONTRADICTS` edge.

Useful properties:

- `contradiction_type`: identity, time, location, relationship, contact_detail, affective, metadata, other.
- `severity`: low, medium, high.
- `status`: detected, needs_clarification, resolved, ignored.
- `reason`
- `detected_by`: memory_writer, llm_judge, user, system.
- `detected_at`
- `resolved_at`
- `resolution_summary`
- `metadata`

Contradiction records store decisions from an agent-invoked contradiction judge. The judge should be invoked when a memory-writing agent, after receiving focused graph context, has a grounded doubt that a proposed write conflicts with existing memory.

The graph layer should not try to prove contradiction through fixed rules. It should preserve the judged decision, severity, source references, and recommended resolution path.

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
- `PERCEIVES`: User/Person to Perception.
- `PERCEPTION_OF`: Perception to any memory-bearing target entity or relationship context.
- `HAS_RELATIONSHIP_CONTEXT`: User/Person to RelationshipContext.
- `RELATIONSHIP_WITH`: RelationshipContext to any target entity.
- `HAS_RELATIONSHIP_STATE`: RelationshipContext to RelationshipState.
- `HAS_AFFECTIVE_CONTEXT`: Entity, Claim, Source, or RelationshipContext to Perception when affective context needs to be explicit and queryable.
- `MERGED_NODE`: MergeRecord to merged node.
- `CANONICAL_NODE`: MergeRecord to canonical node.
- `MERGED_INTO`: Merged node to canonical node.
- `HAS_CONTRADICTION_RECORD`: Claim, entity, or relationship context to ContradictionRecord.

## Provenance Model

Each graph write should preserve:

- Source identifier.
- Extraction run identifier.
- LLM model and prompt version when applicable.
- Confidence score.
- Whether the fact was user-confirmed.
- Timestamp of creation and last update.

Relationships may need their own provenance, not only nodes. For example, two people can both exist confidently while the relationship between them remains uncertain.

Relationships may also carry affective memory. A simple relationship can store lightweight fields such as `emotional_summary`, `emotional_valence`, `emotional_intensity`, `emotion_tags`, and `original_user_words`. If the relationship needs temporal changes, evidence, contradictions, lifecycle, or a richer description, reify it as a `RelationshipContext` or `Claim`.

## Descriptions And Extensible Metadata

Every memory-bearing node and important relationship should support:

- A human-readable `description`.
- An optional `emotional_summary` when the memory has affective weight.
- Optional `emotion_tags`, `emotional_valence`, and `emotional_intensity` when relevant.
- Optional `original_user_words` when the user's phrasing carries important memory signal.
- Stable typed fields used for filtering and querying.
- A flexible `metadata` object for additional variable information.
- Provenance for metadata when the information is important.

The `metadata` object is useful for information that is real but not yet important enough to promote into the core schema. Examples include personal labels, source-specific attributes, external IDs, temporary analysis scores, display hints, and domain-specific details.

Metadata should not become the primary modeling strategy. If a metadata key becomes frequently queried, used in resolution, or important to the product behavior, it should be promoted to a typed property, relationship, or claim.

Affective information should not be hidden in metadata when it is important. Perceptions, relationship contexts, emotional summaries, and original user wording should be typed fields or dedicated nodes. This rule applies beyond people: places, events, objects, organizations, topics, sources, claims, and relationships can all be emotionally meaningful.

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
