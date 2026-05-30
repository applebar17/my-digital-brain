# Affective Memory

## Purpose

My Digital Brain is not only a graph of facts. It is a graph of remembered experience.

Personal memories carry emotional tone, subjective perception, narrative weight, and original user wording. These elements are not decoration or generic metadata. They are part of the memory itself and should be modeled so future retrieval can bring back not only what happened, but how the memory feels to the user.

This is not only valid for people. Any memory-bearing node or important relationship can carry affective weight: a person, place, event, organization, object, topic, source, claim, project, or relationship between entities.

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

Other examples are equally important:

- A place remembered as comforting, unsafe, nostalgic, or liberating.
- A project remembered as stressful but meaningful.
- An object associated with grief, pride, identity, or family history.
- An organization remembered as oppressive, energizing, prestigious, or chaotic.
- A topic remembered as exciting, boring, painful, or triggering.
- An event remembered as humiliating, joyful, confusing, or transformative.

## Product Principle

Affective memory is core to the product.

The system should not behave like a cold factual database. When relevant, graph retrieval should return emotional summaries, perceptions, relationship contexts, and original wording alongside entities and relationships.

This makes answers like "what happened with Alessandro?", "why do I care about that place?", or "what did that project mean to me?" richer than a list of facts. The answer can reflect the emotional shape of the memory while staying grounded and honest about what is user-stated versus inferred.

## Core Concepts

### Perception

A subjective view held by the user about any graph target, including a person, relationship, event, place, organization, object, topic, source, claim, project, or profile-relevant memory.

Examples:

- The user felt Alessandro's personality traits as oppressive.
- The user remembers a place as comforting.
- The user sees a project as stressful but meaningful.
- The user associates an object with grief and nostalgia.
- The user remembers an organization as prestigious but emotionally draining.

Perception is not objective truth about the target. It is the user's experienced truth.

### RelationshipContext

A memory object describing an emotionally or narratively meaningful relationship over time. In a personal brain this is usually between the user and another entity, but the target can be a person, place, organization, project, object, topic, or any other meaningful memory anchor.

Examples:

- Great friendship during teenage years, now low contact.
- Former colleague with high trust.
- Family relationship with unresolved tension.

Relationship context can connect people, organizations, places, projects, or topics, but it is especially important for people.

For simple graph edges, affective fields can live directly on the relationship. When the relationship needs history, evidence, contradictions, temporal changes, or a rich emotional description, model it as a `RelationshipContext` node instead of a bare edge.

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

### Affective Fields On Any Memory Target

Any memory-bearing node and any important relationship may include lightweight affective fields:

- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`

These fields are useful for retrieval and LLM context building. They should stay grounded in source evidence. If the affective signal becomes complex, disputed, temporally changing, or important enough to query directly, promote it into a `Perception`, `RelationshipContext`, or `Claim`.

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
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `metadata`

## Suggested Relationships

- `PERCEIVES`: User/Person to Perception.
- `PERCEPTION_OF`: Perception to any memory-bearing target entity or relationship context.
- `HAS_RELATIONSHIP_CONTEXT`: User/Person to RelationshipContext.
- `RELATIONSHIP_WITH`: RelationshipContext to any target entity.
- `HAS_AFFECTIVE_CONTEXT`: Entity, Claim, Source, or RelationshipContext to Perception when a target needs explicit affective context.
- `SUPPORTED_BY`: Perception or RelationshipContext to Source.
- `DERIVED_FROM`: Perception or RelationshipContext to Source or ExtractionRun.

## Modeling Rules

- Do not store subjective perceptions as objective properties on the target entity.
- Do not label a person as "oppressive"; store that the user perceived some traits as oppressive.
- Do not restrict affective memory to people. Places, events, objects, topics, organizations, sources, claims, and relationships can all carry emotional memory.
- Do not label a place, project, or organization as objectively "stressful" unless that is an external fact. Store that the user experienced it as stressful.
- Preserve emotionally meaningful descriptions as first-class fields, not only as metadata.
- Mark whether affective information is user-stated or LLM-inferred.
- Treat user-stated affective memory as stronger than LLM-inferred or system-derived summaries.
- Do not ask LLMs to invent numeric confidence for affective memory in the first version; use provenance, source links, and user confirmation instead.
- Use privacy levels conservatively; perceptions about people are usually private or sensitive.
- Preserve temporal context when the emotional state changed over time.
- Let later memories update, nuance, dispute, or soften earlier perceptions.
- For relationship affect, use direct relationship properties only for simple summaries. Use `RelationshipContext` or `Claim` nodes when the relationship itself needs provenance, lifecycle, time, contradiction handling, or retrieval as a memory object.

## Retrieval Behavior

When answering questions about a person, event, place, object, topic, organization, source, claim, or relationship, retrieval should include affective context when relevant:

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

## Relationship State History

Complex relationships can evolve through many states. A relationship with an ex, family member, close friend, organization, project, or place can move through closeness, rupture, distance, reconnection, ambivalence, and many other states over years.

The graph should support a diary-like state history:

- `RelationshipContext`: stable relationship memory object.
- `RelationshipState`: one dated relationship state.
- `HAS_RELATIONSHIP_STATE`: RelationshipContext to RelationshipState.
- `RELATIONSHIP_WITH`: RelationshipContext to the target entity.

`RelationshipState` should be flexible and sparse. It may contain only a short description and date, or it may include status, closeness, emotional summary, emotion tags, original user words, source links, and temporal fields.

This avoids forcing every relationship update into a rigid taxonomy while still making current status and historical evolution queryable.
