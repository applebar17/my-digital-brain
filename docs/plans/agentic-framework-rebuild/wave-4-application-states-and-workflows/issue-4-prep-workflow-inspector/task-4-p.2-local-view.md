# Task 4.P.2 — show the workflow and selected run locally

**Status: Complete**

## User story

As the product owner building ingestion, I want a standalone local page to
inspect the assembled workflow and open each state's configuration without
reading code or raw JSON.

## What and why

Serve a read-only page from a local Python server over the workflow object
assembled by the caller. Render agentic and deterministic steps distinctly,
their dependencies, and a detail panel for description, DTO fields, configured
main/reasoning/planning calls, current prompt text, and toolbox contracts.
The page does not add an application frontend route or run-trace overlay.

The initial layout may be a simple graph or connected sequence with selectable
cards. It should remain understandable before adopting a visual editor or a
new graph package.

## Where and communication

- Local Python server and HTML under `src/product/dev/`, bound only to loopback.
- Consume Task 4.P.1's typed composition DTO. Do not embed a separate workflow
  map in the page.
- A direct Python-module command assembles the current provider-free application
  configuration and serves it through the same inspection contract.

## Verification

Open the loopback page and confirm the current states, tools, DTOs, stage flags,
and workflow steps match the assembled application configuration. Select an AI
state and verify its prompt and typed contracts. There is no selected-run
behavior in this slice.
