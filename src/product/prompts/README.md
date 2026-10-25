# Product prompts

This package owns the product's exact-version prompt loading and rendering
boundary. Application composition injects a `PromptTemplateSource`; local
development uses `FilePromptTemplateSource`, while a future database-backed
source can implement the same protocol without changing agentic states.

## Modules

- `models.py`: prompt reference, render context, template, snapshot,
  rendered-prompt DTOs, and the injectable source protocol.
- `sources.py`: the local file-backed source implementation.
- `renderer.py`: literal `{{ name }}` substitution and checksums.
- `service.py`: the small resolution service used by concrete states.
- `templates/`: the only file-backed production prompt bodies.

No source chooses a latest version or silently falls back to another template.
Composition supplies the exact `PromptReferenceDTO` used by a state.
