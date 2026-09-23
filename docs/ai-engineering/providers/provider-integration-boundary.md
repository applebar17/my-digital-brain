# Provider integration boundary

## Purpose

Provider adapters make external AI capabilities available to the provider-neutral
AI runtime. They translate application DTOs to and from an SDK or HTTP API; they
do not contain memory-ingestion, graph, workflow, or chat-product behavior.

The initial supported integration direction is OpenAI and Azure OpenAI behind
the same application-facing contracts. Embedding and speech-to-text providers
follow the same boundary.

## Capability contracts

The provider layer may implement these focused capabilities:

- LLM conversation calls, including structured outputs and tool declarations.
- Provider tool-call and tool-output serialization, preserving provider-issued
  call identifiers exactly.
- Embedding generation for supplied deterministic embedding documents and
  queries.
- Speech-to-text for supplied audio artifacts, returning a transcript and any
  provider-supported confidence or segment information.

The caller selects the model route, prompt snapshot, structured-output DTO,
toolbox, and safe input payload. The adapter translates that request and
normalizes the response into provider-neutral DTOs. It does not select a graph
tool, build a model context package, parse a domain object from prose, or make
an implicit provider fallback after an error.

## Configuration and trace snapshot

Provider configuration is supplied outside source control. An executable route
may select a provider, deployment or model, endpoint configuration, and
capability-specific settings. Secrets never enter prompt snapshots, DTOs,
application logs, or documentation fixtures.

For each call, runtime observability records the configured provider/model or
deployment identifier, prompt reference and checksum when applicable,
structured-output schema version when applicable, non-secret request settings,
usage metadata when supplied, and a normalized error when one occurs. This is
an execution snapshot, not a second prompt or model registry.

## OpenAI and Azure OpenAI

OpenAI and Azure OpenAI may expose different SDK configuration and deployment
shapes. Their adapters normalize those differences before the runtime sees a
result. A caller must not branch domain logic based on which one is configured.

The adapter conformance boundary is:

```text
provider-neutral request DTO
  -> provider adapter
  -> provider request/response shape
  -> provider-neutral completion, tool-call, usage, or error DTO
```

The canonical tool-call continuation rules are in
[tool-calling protocol](../runtime/tool-calling-protocol.md). Provider adapters
preserve those rules; they do not add a second loop or create application tool
IDs.

## Privacy and media handoff

The application chooses whether a source, redacted projection, transcript, or
other derived artifact is safe to send to a provider according to
[privacy and trust](../../requirements/privacy-and-trust.md). The adapter does
not infer privacy policy from raw data.

For speech-to-text, the media integration supplies the permitted audio artifact
and receives a typed derived transcript result. The application stores and
links the original artifact and transcript before normal ingestion uses the
text. A transcript is evidence; it does not replace the original artifact.

## Errors

A provider failure is normalized into an actionable provider error for the
invoking runtime or deterministic caller. It must retain enough non-secret
detail to diagnose the issue, but it must not trigger hidden model routing,
domain fallback, graph mutation, or a synthetic chat answer.

## Verification

Adapter fixtures should cover tool-call ID preservation, structured-output
normalization, embedding response normalization, speech-to-text result
normalization, usage capture, and non-secret error reporting. Conformance
fixtures must not contain production secrets or raw sensitive source data.
