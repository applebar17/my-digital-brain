# Task 5.2.1 — migrate supported source modules and imports

**Status: Not started**

## User story

As a maintainer, I want all still-supported source modules and their consumers
under the neutral `product` package, so the repository no longer presents
`my_digital_brain` as its Python application identity.

## What and why

Move/adapt the stable modules selected by the census and application needs;
rewrite imports, package discovery, test fixtures, scripts, settings, and
deployment/startup configuration. Do not carry agentic modules marked for
retirement merely to avoid adjusting an import.

## Where

- Entire supported `src/my_digital_brain/` source surface into `src/product/`.
- All in-repository imports, test paths, packaging, scripts, and deployment
  configuration referring to the old Python module name.
- Repository name and external branding are not changed by this source-package
  task.

## Functional communication DTOs

None. This is a namespace migration; public API request/response and persisted
DTO semantics must remain unchanged unless separately approved.

## Dependencies and acceptance

- Depends on Task 5.1.2 and reviewed census dispositions.
- All supported package imports resolve under `product`.
- External API routes and persisted data contracts remain compatible.
- Logs remain ignored and are not staged as migration artifacts.
