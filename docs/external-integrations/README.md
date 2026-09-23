# External integrations

Contracts and policies for systems outside the application boundary.

## Contents

- [LLM integration](llm-integration.md): provider integration direction.
- [Media ingestion](media-ingestion.md): future media processing and input.
- [Telegram](telegram.md): chat-channel integration.

Provider-neutral runtime rules belong in [AI engineering](../ai-engineering/README.md);
this folder documents the integration-specific concerns.

## Temporary documentation migration ledger

| File | Transaction action |
| --- | --- |
| `llm-integration.md` | Extract current provider-specific configuration and adapter concerns to `ai-engineering/providers/`, then delete this duplicate source. |
| `media-ingestion.md` | Keep as a functional integration requirement; refresh only its links. |
| `telegram.md` | Keep as a functional channel-integration requirement; refresh only its links. |

This table is removed once the provider extraction is complete.
