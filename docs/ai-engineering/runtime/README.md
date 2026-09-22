# AI runtime

This folder specifies the provider-neutral execution loop: valid transcripts,
tool execution, nested agent tools, continuation, and terminal results.

## Contents

- [Agentic history session](agentic-history-session.md): centralized shared and
  state-local history ownership across direct and nested agentic invocations.
- [Agentic state framework](agentic-state-framework.md): reusable internal LLM
  conversations, their caller contract, toolbox configuration, and nested
  agent-state invocation.
- [Tool-calling protocol](tool-calling-protocol.md): the canonical lifecycle
  and invariants for every provider turn.

## Rule of interpretation

The runtime is an orchestration mechanism, not a place for ingestion, graph,
clarification, or UI-specific rules. Those concerns belong to registered tools
and application services.
