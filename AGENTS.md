# Repository guidance

My Digital Brain is a personal memory graph application. This file is the
repository-level entry point for contributors and coding agents. Detailed
requirements have one canonical owner; use the indexes below before changing a
behavior and update the owning document when that behavior changes.

## Start with the documentation index

- [Documentation index](docs/README.md): navigates product, technical,
  architecture, AI engineering, flows, and other documentation.
- [Technical principles](docs/requirements/technical/technical-principles.md):
  owns scope discipline, minimum design, and the rule that each behavior has
  one canonical specification and one active implementation.
- [Documentation conventions](docs/documentation-conventions.md): owns
  documentation structure, indexing, maintenance, and DTO/annotation-first
  boundaries.
- [AI engineering index](docs/ai-engineering/README.md): indexes the canonical
  AI contracts, runtime, states, providers, prompts, and evaluation guidance.
- [System architecture](docs/architecture/system-architecture.md): owns system
  components, boundaries, external services, and deployment posture.
- [Deterministic agentic workflows](docs/architecture/deterministic-agentic-workflows.md):
  owns workflow execution and handoff rules.
- [Memory-ingestion workflow map](docs/architecture/memory-ingestion-workflow-map.md):
  documents the current AI/code flow, state sequence, and handoffs.

## Working principles

- Follow the user's accepted requirements and priorities. Do not add
  unrequested behavior or requirements. If an improvement seems useful, explain
  its rationale and benefits as a proposal; let the user define whether to add
  it.
- Keep solutions as simple as possible while meeting the accepted requirement.
  Handle complexity when an accepted requirement calls for it.
- Do not add duplicate coding logic, parallel implementations, or legacy code
  unless the user explicitly requests it. Keep source files cohesive and slim;
  fewer than 500 lines is a rule of thumb, not a hard limit.
- Treat documentation as the navigational entry point and maintain one source
  of truth per behavior. Index the canonical owner instead of copying its
  rules. Keep documentation current when implementation or decisions change.
- When user requirements and documentation disagree, identify the exact gap,
  follow the user's stated priority, and establish one coherent decision with
  the user. Update the canonical document and its indexes to reflect that
  decision.
- For AI engineering questions, consult the Azure OpenAI documentation MCP
  when it is available. Otherwise, use relevant official Azure OpenAI
  documentation. Project-specific behavior remains governed by this
  repository's canonical documentation and accepted user requirements.
- Use human-first prose and give enough context that readers can understand
  code references without already knowing the codebase. Concise bullets are
  welcome when each bullet is self-contained.

## Scoped instructions

- Documentation work: [docs/AGENTS.md](docs/AGENTS.md)
- Source code work: [src/AGENTS.md](src/AGENTS.md)
