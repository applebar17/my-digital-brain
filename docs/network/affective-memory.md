# Affective Memory

## Purpose

My Digital Brain is not only a graph of facts. It is a graph of remembered experience.

Personal memories carry emotional tone, subjective perception, narrative weight, and original user wording. These elements are not decoration or generic metadata. They are part of the memory itself and should be modeled so future retrieval can bring back not only what happened, but how the memory feels to the user.

Example:

```text
I had a great relationship with Alessandro during my teenage years, but now we do not talk that much. I have always felt some of his personality traits as oppressive.
```

The system should preserve:

- Alessandro as a person.
- The historical relationship context.
- The change from closeness to low contact.
- The user's subjective perception of oppressive traits.
- The emotional contrast between warmth, distance, and discomfort.
- The user's own words when available.

## Product Principle

Affective memory is core to the product.

The system should not behave like a cold factual database. When relevant, graph retrieval should return emotional summaries, perceptions, relationship contexts, and original wording alongside entities and relationships.

This makes answers like "what happened with Alessandro?" richer than a list of facts. The answer can reflect the emotional shape of the memory while staying grounded and honest about what is user-stated versus inferred.

## Core Concepts

### Perception

A subjective view held by the user about a person, relationship, event, place, organization, object, or topic.

Examples:

- The user felt Alessandro's personality traits as oppressive.
- The user remembers a place as comforting.
- The user sees a project as stressful but meaningful.

Perception is not objective truth about the target. It is the user's experienced truth.

### RelationshipContext

A memory object describing the user's relationship with another entity over time.

Examples:

- Great friendship during teenage years, now low contact.
- Former colleague with high trust.
- Family relationship with unresolved tension.

Relationship context can connect people, organizations, places, projects, or topics, but it is especially important for people.

### Emotional Summary

A compact natural-language summary of the emotional tone of a memory or relationship.

Examples:

- "Warm past bond mixed with distance now."
- "Respect and admiration, but also pressure."
- "A place associated with freedom and nostalgia."

Emotional summaries are useful for LLM retrieval because they preserve the narrative and affective signal of memory.

### Original User Words

When the user expresses a memory in a vivid or emotionally meaningful way, the system should preserve the original wording or a short excerpt reference.

The user's words are often more important than a normalized label.

## Suggested Node Types

### Perception

Useful properties:

- `id`
- `description`
- `perception_type`
- `target_type`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `source_kind`: user_stated, llm_inferred, system_derived.
- `valid_from`
- `valid_to`
- `time_precision`
- `confidence`
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `metadata`

### RelationshipContext

Useful properties:

- `id`
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
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `metadata`

## Suggested Relationships

- `PERCEIVES`: Person to Perception. Usually the user to a perception.
- `PERCEPTION_OF`: Perception to target entity.
- `HAS_RELATIONSHIP_CONTEXT`: Person to RelationshipContext.
- `RELATIONSHIP_WITH`: RelationshipContext to target entity.
- `HAS_AFFECTIVE_SUMMARY`: Entity or RelationshipContext to Perception, if summaries are modeled as perception-like objects.
- `SUPPORTED_BY`: Perception or RelationshipContext to Source.
- `DERIVED_FROM`: Perception or RelationshipContext to Source or ExtractionRun.

## Modeling Rules

- Do not store subjective perceptions as objective properties on the target entity.
- Do not label a person as "oppressive"; store that the user perceived some traits as oppressive.
- Preserve emotionally meaningful descriptions as first-class fields, not only as metadata.
- Mark whether affective information is user-stated or LLM-inferred.
- Use privacy levels conservatively; perceptions about people are usually private or sensitive.
- Preserve temporal context when the emotional state changed over time.
- Let later memories update, nuance, dispute, or soften earlier perceptions.

## Retrieval Behavior

When answering questions about a person, event, place, or relationship, retrieval should include affective context when relevant:

- Perceptions connected to the entity.
- Relationship contexts involving the entity.
- Emotional summaries.
- Original user wording or source references.
- Temporal changes in emotional tone.
- Whether affective statements are user-stated or inferred.

The answer should not overstate inferred emotions. It should phrase them carefully:

```text
You described the relationship as very positive during your teenage years, but with much less contact now. You also wrote that you felt some of Alessandro's traits as oppressive.
```

## Future Research Direction

Future versions may explore whether personality traits and affective memory can support a model that responds more similarly to the user. This is a research direction, not an MVP behavior.

For now, the system should preserve affective memory and profile memory in a way that makes such experimentation possible later, without pretending to clone the user or treating inferred traits as permanent identity.
