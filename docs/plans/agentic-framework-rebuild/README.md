# Agentic framework rebuild

**Status: In progress**

## Purpose

Rebuild the agentic framework and application pipeline in a new code layer
with separate imports, treating most current agentic implementation as
reference material. Keep stable application boundaries where appropriate, and
remove superseded agentic code after the replacement is verified. The exact
retirement set and implementation waves are not decided until Wave 0 is
complete.

This plan is the work breakdown; design sources remain in
[AI engineering](../../ai-engineering/README.md),
[architecture](../../architecture/README.md),
[flows](../../flows/README.md), and the relevant domain documentation.

## Waves

- [Wave 0 — current-pipeline census](wave-0-census/README.md): inspect the
  current agentic package, its direct integrations, contracts, tests, and
  runtime behavior. Classify each in-scope file by rebuild value and target
  disposition. No implementation waves are defined yet.

## Rebuild constraints

- New framework code has a distinct package location and import boundary.
- The current implementation is not presumed to be the target architecture.
- Reuse behavior and stable external contracts only after explicit review;
  do not copy old internal structure by default.
- DTOs and annotated function boundaries are identified before their
  implementation tasks.
- Keep only stable non-agentic application boundaries that remain needed; do
  not retain parallel or compatibility agentic runtimes after cutover.
- Wave 0 documents evidence and disposition proposals; implementation waves
  follow only after its census is complete and reviewed.

## Collaboration rule

Before each implementation task, discuss its purpose, DTOs and function
signatures, affected files, dependencies, and verification with the user. Do
not begin that task until its scope and approach are agreed.
