# Privacy And Trust

## Purpose

The system stores personal memory. It must distinguish between what it knows, how it knows it, how sensitive it is, and whether it can be used with external services.

## Trust Levels

Stored facts should expose a trust level or trust source:

- `user_confirmed`: explicitly confirmed by the user.
- `source_stated`: directly stated in a source.
- `llm_inferred`: inferred by a model from evidence.
- `system_derived`: derived by deterministic logic.
- `externally_enriched`: returned by an external tool or provider.
- `contradicted`: conflicts with another fact.
- `stale`: possibly outdated.

Trust level should influence answers. A low-confidence or inferred memory should not be phrased as certain fact.

## Privacy Zones

Suggested privacy zones:

- `normal`: can be used in ordinary retrieval and answers.
- `private`: can be retrieved for the owner but should avoid unnecessary exposure.
- `sensitive`: requires stricter confirmation, logging, and provider controls.
- `local_only`: should not be sent to cloud services.
- `hidden`: excluded from normal answers unless explicitly requested.

Privacy zones can apply to sources, entities, relationships, claims, contact points, profile memories, and metadata.

## Sensitive Categories

Potentially sensitive data includes:

- Contact details.
- Home addresses.
- Health information.
- Financial information.
- Work-confidential information.
- Relationship details.
- Political, religious, or identity-related information.
- Profile memories and personality traits.

The system should be conservative when storing, enriching, or sending this data to external providers.

## Answer Behavior

Answers should adapt to trust and privacy:

- Prefer confirmed and current facts.
- Label inferred, stale, or contradicted facts.
- Avoid exposing sensitive facts unless relevant.
- Use local-only facts only in local-safe contexts.
- Provide source/evidence references when useful.

Example:

```text
I have a newer phone number for Luca from March 2026, but it is not user-confirmed yet.
```

## Provider Boundaries

Before sending data to cloud LLMs or enrichment providers, the system should check:

- Privacy zone.
- User policy.
- Provider retention settings.
- Whether redaction is possible.
- Whether local processing is available.

## Graph And Backup Security

Graph database authentication should be enabled even for local-first deployment. The graph database should not be exposed outside the local container or trusted network unless explicitly needed.

Authentication protects the running database service. It does not protect copied database files, dumps, or exported backup packages. Those should be encrypted separately.

Secure export and restore should include:

- Authenticated export initiation.
- Encrypted backup package.
- Manifest with schema version, timestamps, included data stores, and checksums.
- Optional manifest signature.
- Short-lived remote download authorization if backups are stored remotely.
- Checksum verification before restore.
- Clear policy for where encryption keys or passphrases are stored.

## Lightweight UX

Privacy and trust should not become a complicated management interface. Most interactions should happen through simple chat prompts and clear answer wording:

- "This looks sensitive. Should I store it?"
- "I found a conflict. Which one should I trust?"
- "This came from a map lookup, not from your own memory."
