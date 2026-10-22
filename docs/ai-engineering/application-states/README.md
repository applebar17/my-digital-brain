# AI application states

## Purpose

This folder maps application-specific capabilities onto the reusable AI runtime
framework. It identifies which capabilities are deterministic services/tools,
LLM-only states, or dynamic agentic states and specifies their application-level
responsibilities.

## Contents

- [State and tool taxonomy with current map](state-and-tool-taxonomy.md):
  terminology, invocation patterns, the `query_memory` example, target
  classification of current capabilities, and required state documentation.
- [Conversation entry state](conversation-entry-state.md): top-level chat
  responsibility and its two agentic tools.
- [Memory query state](memory-query-state.md): deterministic retrieval/hydration
  followed by a grounded LLM query state.
- [Tools that request user input](user-interaction-tools.md): backend-owned
  deadlines and answer/timeout completion for UI-waiting tools.
- [Ingestion application states](ingestion/README.md): behavioral conventions,
  typed handoffs, and prompt boundaries for the phased ingestion workflow.

## Status

These documents specify intended application integration. They do not imply
that every documented capability is implemented. Prompt templates, toolbox
contracts, and runtime mechanics remain owned by their dedicated AI-engineering
documents.
