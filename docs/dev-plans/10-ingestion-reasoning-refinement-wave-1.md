# Ingestion Reasoning Refinement Wave 1

## Summary

Refine memory ingestion from the current planner-first shape into a
reasoning-first, entity-first, relationship-second pipeline.

The purpose of this wave is to reduce duplicated entities, invalid candidate
fields, missing relationships, and relationship candidates that point to
ambiguous or uncreated nodes.

Locked baseline:

- Source context is retrieved before reasoning.
- Reasoning, planning, candidate preparation, validation, and write execution
  are separate activities.
- Entity work happens before relationship work.
- Entity creation is staged until duplicate handling and deterministic
  validation have run.
- Relationship planning receives the resolved entity map and must not invent
  unresolved endpoints.
- V1 keeps validation simple and deterministic. Qualitative duplicate judging,
  richer merge decisions, and user confirmation workflows are reserved for a
  later wave.

## Target Flow

```text
source
  -> whole-source hybrid graph retrieval
  -> compact Graph Context Pack
  -> structured reasoning checkpoint

  -> entity plan
  -> entity candidates
  -> duplicate judge / entity validation
  -> resolved entity map + staged entity create/update ops

  -> relationship plan using resolved entity map
  -> relationship candidates
  -> relationship validation
  -> write
```

Relationship planning may discover a required endpoint that the entity track
missed:

```text
relationship plan
  -> missing_entity_required?
      -> supplemental entity candidate
      -> duplicate judge / entity validation
      -> update resolved entity map
  -> relationship candidates
```

## Locked Principles

1. **Graph context v1 stays simple.**

   Do not generate multiple natural-language graph queries in wave 1. Embed the
   whole source text and retrieve the top-k graph items through hybrid search.

2. **The Graph Context Pack is compact and model-facing.**

   It should contain useful nearby graph state, not raw graph dumps. It should
   summarize relevant existing entities, aliases, known relationships, nearby
   memories or events, and potential duplicate hints.

3. **Reasoning comes before planning.**

   The first model-backed ingestion step is a structured reasoning checkpoint,
   not an extraction planner.

4. **Reasoning clarifies future doubts.**

   The reasoning output must help later steps understand aliases, entity
   identity, user-specific relationships, salience, ambiguous wording, and
   storage implications.

5. **Reasoning is structured interpretation, not graph mutation.**

   It does not write memory, decide database IDs, emit graph write operations,
   or bypass validation.

6. **Planning and extraction are split by target type.**

   Entity planning/extraction and relationship planning/extraction are separate
   model tasks with separate contracts.

7. **Entity work happens first.**

   Relationships are planned only after the entity track has produced a
   resolved entity map or staged entity operations.

8. **Entity creation is staged.**

   Candidate entities are not durable nodes until duplicate handling and
   deterministic validation complete.

9. **Duplicate handling is a required process slot.**

   Before injecting new candidates, the system must compare them against the
   retrieved graph context and current graph state.

10. **V1 duplicate handling is conservative.**

   Wave 1 reserves the duplicate-judge slot, but only deterministic validation
   is required initially. Qualitative duplicate judging and user confirmation
   are later work.

11. **Duplicate merge behavior is a target capability.**

   When a candidate is judged to be a duplicate in a later wave, useful
   information should transfer to the existing node: aliases, relationships,
   additional metadata, log or activity references, and refreshed embeddings.

12. **Relationship planning uses resolved references only.**

   The relationship planner receives the resolved entity map and should produce
   relationships only between known local refs or existing graph aliases.

13. **Missing endpoints are explicit.**

   If a relationship requires an entity that was not created or resolved, the
   relationship step emits `missing_entity_required` instead of inventing an
   endpoint silently.

14. **V1 validation is deterministic.**

   Validation should check schema compatibility, required fields, forbidden
   fields, allowed ontology values, resolved endpoints, and exact duplicate
   edges. It should not attempt qualitative semantic judging yet.

15. **No full qualitative traceability requirement in v1.**

   Evidence and source grounding remain useful, but wave 1 does not require a
   complete qualitative trace-back system or LLM judge for every write.

16. **The process should reduce hallucination through context shaping.**

   Each step receives only the context required for its responsibility:
   reasoning receives the source and compact graph context; entity planning
   receives reasoning focused on entities; relationship planning receives the
   resolved entity map and relationship reasoning.

## Step Responsibilities

### 1. Whole-Source Hybrid Graph Retrieval

Kind: backend process.

Input:

- normalized source text or transcript
- current time and timezone
- owner/session scope and privacy/lifecycle filters

Behavior:

- embed the whole source text
- run hybrid graph retrieval with top-k limits
- hydrate relevant graph records
- compact entities and relationships into model-facing aliases

Output:

- `GraphContextPack`

Out of scope:

- query fan-out
- generated natural-language search queries
- qualitative duplicate judgment

### 2. Graph Context Pack

Kind: backend-built context object.

It should include:

- short graph aliases, not raw UUID-heavy payloads
- existing relevant entities
- aliases and nicknames
- known relationships and relationship contexts
- nearby events or memories when useful
- potential duplicate hints from exact, alias, fuzzy, or hybrid retrieval
- compact source/evidence summaries when already available

It should exclude:

- raw technical metadata
- full graph JSON
- provider traces
- unrelated neighborhoods
- backend-only IDs when aliases are enough

### 3. Structured Reasoning Checkpoint

Kind: model-backed structured reasoning step.

Purpose:

- interpret the source in the presence of graph context
- make ambiguity explicit for later steps
- decide whether mentions are entities, aliases, relationship hints, or
  contextual details
- identify likely user-related storage implications

Required output themes:

- entity understanding
- alias and nickname interpretation
- candidate duplicate concerns
- relationship hypotheses
- node-versus-metadata recommendations
- user/owner involvement
- missing context or ambiguity
- storage cautions

Example expected reasoning:

```text
New entity candidate: Matteo Mercoldi.
The user also calls him "Merc".
"Merc" should be treated as an alias/nickname of Matteo Mercoldi, not as a
separate Person node.
```

The checkpoint must not output hidden chain-of-thought. It should output
structured decision notes, interpretations, and storage implications.

### 4. Entity Plan

Kind: model-backed structured plan.

Input:

- source text
- Graph Context Pack
- structured reasoning checkpoint

Output:

- entity-only ingestion plan

Allowed:

- identify which entities must be prepared
- identify which mentions should become aliases
- identify which details should remain metadata or event description
- request clarification only when entity ambiguity blocks useful storage

Forbidden:

- relationship candidates
- graph write operations
- backend IDs
- unsupported node fields

### 5. Entity Candidates

Kind: focused structured extraction.

Input:

- entity plan
- source text
- entity-focused reasoning
- graph aliases and duplicate hints

Output:

- schema-compatible entity candidates

Candidate entities must use scoped local refs. They must not use backend-owned
IDs or arbitrary metadata dicts.

### 6. Duplicate Judge / Entity Validation

Kind: backend process in v1; future hybrid process later.

Wave 1 deterministic checks:

- schema fields are allowed for the candidate type
- required fields are present or explicitly unknown
- aliases are accepted only on node types that support aliases
- local refs are unique
- obvious exact duplicate aliases/names are detected
- candidate entity type is allowed

Future target outcomes:

```text
confirmed duplicate -> update existing node
suspected duplicate -> ask user confirmation
not duplicate -> create new node
```

Future duplicate application behavior:

- transfer aliases
- transfer useful relationships
- transfer metadata or activity references
- refresh embeddings for the canonical node

### 7. Resolved Entity Map

Kind: backend-built handoff object.

Purpose:

- give later steps stable references for relationship planning
- prevent relationship candidates from pointing to unresolved endpoints

It maps:

```text
local entity ref -> existing graph alias or staged create/update op
```

### 8. Relationship Plan

Kind: model-backed structured plan.

Input:

- source text
- relationship-focused reasoning
- resolved entity map
- compact graph relationships from the context pack

Output:

- relationship-only ingestion plan

Allowed:

- plan relationships between resolved/staged entities
- choose whether a relationship belongs as a direct edge,
  `RelationshipContext`, `Perception`, event participation, place link, or
  metadata suggestion
- emit `missing_entity_required` when an endpoint is missing

Forbidden:

- free creation of new entities
- relationships to unknown refs
- unsupported edge types
- graph write operations

### 9. Relationship Candidates

Kind: focused structured extraction.

Output:

- schema-compatible relationship candidates
- relationship contexts, perceptions, event participation links, or place links
  when those are the correct storage shapes

Relationship candidates must reference only:

- resolved entity local refs
- existing graph aliases provided in context
- staged entity refs from the resolved entity map

### 10. Relationship Validation

Kind: backend process.

Wave 1 deterministic checks:

- endpoints resolve
- relationship type is allowed
- relationship kind/detail fit the allowed ontology
- exact duplicate edge is not created
- forbidden fields are absent
- required temporal or descriptive fields are present when the storage shape
  requires them

### 11. Write

Kind: backend process.

Only validated operations become persistent graph writes.

The write step owns:

- generated IDs
- source refs
- timestamps
- evidence refs
- lifecycle state
- graph persistence
- vector refresh triggers when implemented

## Prompt And Contract Requirements

Prompting should be detailed but not overloaded. Each prompt must describe only
the current step's responsibility.

Required examples:

- nickname/alias handling:

  ```text
  "Merc" -> alias of Matteo Mercoldi, not a separate Person.
  ```

- family relationship:

  ```text
  "mio fratello Lorenzo" -> Person Lorenzo plus owner-to-Lorenzo family
  relationship with relationship_detail="brother".
  ```

- ambiguous social group:

  ```text
  "il suo gruppo" -> SocialCircle candidate only if the group is meaningful;
  do not emit unsupported fields such as aliases when the target schema does
  not allow them.
  ```

- low-salience detail:

  ```text
  "uova con zucchine e peperoni" -> event detail unless the object is durable,
  recurring, or semantically important.
  ```

The prompts should include explicit rules for:

- entity versus detail
- alias versus new entity
- relationship versus metadata
- user/owner as relationship endpoint
- SocialCircle field restrictions
- unresolved endpoint handling
- no graph mutation from model output

## V1 Scope

Wave 1 should implement or align:

- whole-source hybrid graph retrieval for ingestion context
- compact `GraphContextPack`
- ingestion-specific structured reasoning checkpoint
- entity-only planning
- entity candidate preparation
- staged entity resolution map
- deterministic entity validation
- relationship-only planning after entity resolution
- relationship candidate preparation
- deterministic relationship validation
- `missing_entity_required` loop
- write execution from validated backend operations only

## Explicitly Out Of Scope For Wave 1

- generated natural-language graph query fan-out
- qualitative LLM duplicate judge
- user confirmation UI for suspected duplicates
- full merge/split application logic
- broad prompt optimization framework
- source-level qualitative trace-back for every decision
- ontology expansion beyond the currently allowed node and relationship types
- replacing the graph/vector retrieval architecture

## Implementation Order

1. Add or update structured contracts for `GraphContextPack`,
   `StructuredReasoningCheckpoint`, entity plan, relationship plan,
   `ResolvedEntityMap`, and `missing_entity_required`.
2. Build whole-source hybrid retrieval context for ingestion.
3. Compact retrieved graph state into the Graph Context Pack.
4. Plug the structured reasoning checkpoint before planning.
5. Split planning into entity plan and relationship plan.
6. Run entity candidate preparation before relationship candidate preparation.
7. Build the resolved entity map after deterministic validation/resolution.
8. Make relationship planning consume only the resolved entity map.
9. Add deterministic validation for entity fields, relationship endpoints, and
   allowed ontology values.
10. Route `missing_entity_required` into supplemental entity candidate handling.
11. Keep old ingestion flow available as fallback until UAT proves the new flow.
12. Add focused UAT cases and report outputs for duplicate and relationship
   quality.

## UAT Signals

Wave 1 should improve the following visible behaviors:

- aliases such as `Merc` do not become duplicate people when a canonical person
  is available
- family wording such as `mio fratello` creates or retrieves the brother node
  and owner relationship context
- relationships are not dropped because endpoints were created later
- relationship candidates do not point to unknown refs
- SocialCircle candidates do not contain unsupported fields such as `aliases`
- low-salience objects are less likely to become standalone nodes
- graph search for relationship-heavy queries has relevant connected nodes and
  edges to render

## Future Follow-Ups

- Explore generated natural-language graph query fan-out after whole-source
  retrieval is stable.
- Design the qualitative duplicate judge.
- Design user confirmation for suspected duplicates and proposed merges.
- Implement non-destructive duplicate merge application.
- Re-embed canonical nodes after duplicate updates and relationship transfers.
- Add evaluation examples for alias handling, kinship, social circles,
  cohabitants, event participants, and low-salience objects.
