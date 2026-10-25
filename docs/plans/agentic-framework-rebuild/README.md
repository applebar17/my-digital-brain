# Product runtime and agentic framework rebuild

**Status: In progress**

## Purpose

Rebuild the runtime under a neutral `product` Python namespace. Keep the
provider/client layer, reusable agentic framework, and product-specific states
and workflow in distinct packages. Migrate only needed application services
and stable API boundaries; retire the old `my_digital_brain` source tree after
the replacement is integrated and verified. Wave 0's evidence informs this
proposal; implementation scope remains reviewed one issue at a time.

## Proposed package ownership

| Target package | Responsibility |
| --- | --- |
| `product.ai.ai_clients` | Provider adapters, request parameters, provider transcript, and tool loop. |
| `product.agentic` | Reusable history session, base state invocation, typed generic tool contracts, and configurable reasoning/planning stages. |
| `product.application.states` | Concrete product agentic states with functional prompts, input/output DTOs, and configured toolboxes. |
| `product.application.tools` | Product-specific typed tools over deterministic services or child states. |
| `product.application.workflows` | Deterministic sequencing and data handoffs among application services and states. |
| `product.api` and product persistence packages | Stable endpoint/storage boundaries adapted to the new runtime. |

The existing `src/my_digital_brain/` package remains the reference/runtime
boundary during migration. Target code uses `src/product/`; there will be no
permanent compatibility namespace. The old source tree is removed after all
required modules, callers, configuration, and tests have moved.

This plan is the work breakdown; design sources remain in
[AI engineering](../../ai-engineering/README.md),
[architecture](../../architecture/README.md),
[flows](../../flows/README.md), and the relevant domain documentation.

## Waves

- [Wave 0 — current-pipeline census](wave-0-census/README.md): inspect the
  current agentic package, its direct integrations, contracts, tests, and
  runtime behavior. **Complete.**
- [Wave 1 — neutral package and client foundation](wave-1-product-and-client-foundation/README.md): establish the target namespace and ensure the selected client layer supports the framework contracts.
- [Wave 2 — generic agentic framework](wave-2-agentic-framework/README.md): implement reusable history, state invocation, typed tools, and configured reasoning/planning stages without product workflow policy.
- [Wave 3 — application capabilities](wave-3-application-capabilities/README.md): demand-driven support work discovered while defining and implementing a state; this is not a blanket service/tool migration gate.
- [Wave 4 — application states and workflows](wave-4-application-states-and-workflows/README.md): deliver one selected workflow as ordered state-by-state vertical slices, deriving DTOs, deterministic functions, tools, and handoffs as each state requires them.
- [Wave 5 — application integration and retirement](wave-5-integration-and-retirement/README.md): connect API/chat boundaries, verify user-visible flows, and retire the old source namespace.

## Application delivery order

Application work is workflow-first, not service-first. Begin with the existing
memory-ingestion workflow, census the states and deterministic steps it needs,
then take each state in execution order. For each state, agree its functional
purpose and input/output before defining its internal DTOs, deterministic
dependencies, model-visible tools, function mappings, and handoffs. Integrate
the state into the workflow and verify its functional behavior before moving to
the next state.

The generic tool contracts and toolbox composition from Wave 2 are established
framework capabilities. Application-specific DTOs, tool schemas, and service
operations remain working proposals until required by an agreed state. Existing
application-state documents are starting references for this review, not an
automatic commitment to every listed tool or field.

## Rebuild constraints

- New code lives under `src/product/`; reusable framework and application
  behavior have separate package ownership.
- The current implementation is not presumed to be the target architecture.
- Reuse behavior and stable external contracts only after explicit review;
  do not copy old internal structure by default.
- DTOs and annotated function boundaries are identified for each state before
  implementing that state's slice; do not predefine application contracts for
  unreviewed states.
- Keep only stable non-agentic application boundaries that remain needed; do
  not retain parallel or compatibility agentic runtimes after cutover.
- Wave 0 is complete. The implementation waves are planning proposals; before
  each issue, discuss and agree its functional behavior, DTOs, scope, and
  verification with the user.

## Development and testing guidelines

- Test functional behavior and communication across meaningful boundaries:
  caller-to-state, state-to-tool/child-state, tool-to-service, and workflow/API
  handoffs where applicable.
- Prefer a small number of scenario tests that show the data passed, the result
  returned, and the externally observable effect. Keep tests readable as
  examples of the intended behavior.
- Do not add micro-tests for package names/imports, trivial getters, private
  helpers, or implementation details that do not protect a functional
  contract. Avoid duplicating coverage already provided by a broader scenario.
- Retain focused tests for critical protocol guarantees that can otherwise
  corrupt a conversation, such as matched tool outputs, recoverable tool
  failures, child-state return to the invoker, and continuation after a human
  answer.
- Add the smallest test set that gives confidence in the task's agreed
  acceptance behavior; do not optimize for line or branch coverage.

## Collaboration rule

Before each implementation task, discuss its purpose, DTOs and function
signatures, affected files, dependencies, and verification with the user. Do
not begin that task until its scope and approach are agreed.
