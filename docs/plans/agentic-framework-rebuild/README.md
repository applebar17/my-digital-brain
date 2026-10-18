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
| `product.agentic` | Reusable history session, base state invocation, typed generic tool contracts, and state-level preparation. |
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
- [Wave 2 — generic agentic framework](wave-2-agentic-framework/README.md): implement reusable history, state invocation, typed tools, and configured preparation without product workflow policy.
- [Wave 3 — application capabilities](wave-3-application-capabilities/README.md): place required deterministic services and product tool adapters under `product`.
- [Wave 4 — application states and workflows](wave-4-application-states-and-workflows/README.md): define functional state contracts and deterministic handoffs, with state-to-state data made explicit.
- [Wave 5 — application integration and retirement](wave-5-integration-and-retirement/README.md): connect API/chat boundaries, verify user-visible flows, and retire the old source namespace.

## Rebuild constraints

- New code lives under `src/product/`; reusable framework and application
  behavior have separate package ownership.
- The current implementation is not presumed to be the target architecture.
- Reuse behavior and stable external contracts only after explicit review;
  do not copy old internal structure by default.
- DTOs and annotated function boundaries are identified before their
  implementation tasks.
- Keep only stable non-agentic application boundaries that remain needed; do
  not retain parallel or compatibility agentic runtimes after cutover.
- Wave 0 is complete. The implementation waves are planning proposals; before
  each issue, discuss and agree its functional behavior, DTOs, scope, and
  verification with the user.

## Collaboration rule

Before each implementation task, discuss its purpose, DTOs and function
signatures, affected files, dependencies, and verification with the user. Do
not begin that task until its scope and approach are agreed.
