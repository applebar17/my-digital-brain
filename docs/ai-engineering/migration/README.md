# AI runtime migration

This folder contains technical assessments that inform migration work. The
work breakdown and wave/task sequencing live in the indexed
[plans area](../../plans/README.md), not in this technical reference section.

## Contents

- [Reference client assessment](reference-ai-clients-assessment.md): what the
  imported `ai_clients` package demonstrates, what must not be copied, and its
  current repository status; claims about current callers must be verified by
  the Wave 0 census before they drive implementation.
- [Agentic framework rebuild plan](../../plans/agentic-framework-rebuild/README.md):
  the current multi-wave planning entry point; Wave 0 is the only defined wave.

## Rules

- This folder records technical assessments and contracts; it does not own
  task-level migration sequencing.
- The plan folder records work sequencing and links to technical sources of
  truth instead of duplicating runtime design.
