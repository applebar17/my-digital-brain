# Metadata Policy Contract

## Purpose

Metadata allows the system to store variable information without changing the graph schema for every new detail. The risk is metadata sprawl: many one-off keys that are hard to query, validate, migrate, or trust.

This contract defines how metadata should be accepted, structured, promoted, and governed.

## Metadata Categories

### Flexible Metadata

Used for optional or experimental attributes.

Examples:

- UI hints.
- Temporary scores.
- Source-specific details.
- Experimental classification results.

### Structured Metadata

Used when data has predictable shape but does not yet deserve a first-class node or property.

Examples:

- Integration payload fragments.
- Domain-specific attributes.
- Derived analysis output.

### Promoted Metadata

Metadata that becomes important enough to move into typed schema.

Promotion should happen when a metadata key is:

- Frequently queried.
- Used in entity resolution.
- Used in retrieval ranking.
- Used in product behavior.
- Exposed prominently in the UI.
- Sensitive or mutable.

## Required Metadata Envelope

Metadata should use a consistent envelope where practical:

```json
{
  "schema_version": "1",
  "namespace": "integration.google_maps",
  "attributes": {
    "example_key": "example value"
  },
  "source_refs": ["source-id"],
  "created_at": "2026-05-24T12:00:00Z",
  "updated_at": "2026-05-24T12:00:00Z",
  "confidence": 0.8,
  "privacy_level": "normal",
  "ttl": null
}
```

## Namespacing

Metadata keys should be namespaced to avoid collisions.

Examples:

- `integration.google_maps.place_id`
- `ui.graph.color_hint`
- `analysis.entity_resolution.score`
- `source.telegram.forwarded_from`

## Promotion Rules

Do not leave these as generic metadata for long:

- Phone numbers.
- Email addresses.
- Physical addresses.
- Provider entity IDs.
- Current location coordinates.
- Current job or role.
- Privacy-sensitive traits.
- Values used by search, ranking, or resolution.

These should become typed properties, relationships, claims, contact points, or external references.

## Validation

Metadata writes should be validated for:

- Allowed namespace.
- JSON-serializable shape.
- Reasonable size.
- Privacy level.
- Source reference when it affects behavior.
- Expiration when the data can become stale.
- Whether it should be promoted instead.

## Runtime Policy

At runtime, metadata can be used for:

- Display.
- Filtering.
- Ranking.
- Enrichment decisions.
- Debugging.

But metadata should not silently drive important behavior unless the metadata key is documented and validated.

## Deletion And Expiration

Metadata can be:

- Updated.
- Expired.
- Superseded.
- Removed.
- Promoted into structured schema.

When metadata has evidence value, prefer superseding or expiring over silent overwrite.
