# External API Integrations

## Goal

Define placeholder integration areas for optional external services without committing to unnecessary complexity before the core memory loop works.

Core model providers and Telegram are owned by other plans:

- OpenAI, Azure OpenAI, speech-to-text, embeddings, and model routing are part of [Backend ingestion pipeline definition](02-backend-ingestion-pipeline.md).
- Telegram is part of [Backend chat interface and DB tooling](03-chat-interface-and-db-tooling.md).

This file is for non-core enrichment, import, sync, and external data integrations.

## Wave 0: Baseline Decisions

- External integrations in this file are optional for MVP.
- Do not duplicate core Telegram or LLM provider work here.
- Add APIs only when they provide clear memory value.
- External data must remain distinguishable from user-provided memory.
- Provider terms, privacy, and freshness constraints matter before storage.

## Wave 1: Placeholder Integration Boundaries

No additional external APIs are required for the MVP beyond the core providers handled in the ingestion and chat plans.

Define placeholder interfaces for:

- Enrichment request shape.
- Provider provenance.
- Runtime lookup versus cached lookup.
- Privacy checks before provider calls.

## Wave 2: Useful Enrichment Integrations

Potential integrations:

- Maps/geocoding provider for place enrichment.
- Contacts provider for future contact sync.
- Calendar import.
- Link/page extraction.
- Document parsing.

Rules:

- Store provider provenance.
- Respect privacy zones.
- Use runtime lookup when persistence is not needed.
- Cache with expiration when freshness matters.
- Avoid treating external results as user-confirmed memory.

## Wave 3: Advanced Integrations

- Mobile contacts sync.
- Location history import.
- Email or messaging export import.
- Photo library metadata import.
- Browser/bookmark ingestion.
- Personal file indexing.

## Risks

- External APIs can leak private context.
- Provider data can be stale or wrong.
- Provider terms may restrict storage or redisplay.
- Integrations can distract from the core memory loop.

## Initial Success Criteria

- Optional integrations are not required for the first memory loop.
- The architecture has a clear place to add maps, contacts, calendar, links, and documents later.
- Sensitive data boundaries are explicit before optional external calls.
- External enrichment results can be represented with provider provenance when added.
