from __future__ import annotations

import re
from pathlib import Path
from string import Formatter
from typing import Any

from my_digital_brain.prompts.active import ACTIVE_PROMPT_TEMPLATES
from my_digital_brain.prompts.models import PromptTemplate

_VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class PromptNotFoundError(FileNotFoundError):
    pass


class PromptRegistry:
    """Code-first prompt registry.

    Active prompts live in ``prompts.active`` as Python constants. File-backed
    templates remain supported for tests, local overrides, and prompts that have
    not yet been migrated:

    ```text
    templates/<prompt_id>/<version>.system.md
    ```

    Rendering supports both `{variable}` and `{{ variable }}` placeholders.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parent / "templates"
        self._use_active_constants = root is None

    def load(self, prompt_id: str, version: str = "v1") -> PromptTemplate:
        if self._use_active_constants and version == "v1":
            template = ACTIVE_PROMPT_TEMPLATES.get(prompt_id)
            if template is not None:
                return PromptTemplate(
                    prompt_id=prompt_id,
                    version=version,
                    template=template,
                )
        path = self._path(prompt_id, version)
        if not path.exists():
            raise PromptNotFoundError(
                f"Prompt template not found: {prompt_id}/{version} at {path}"
            )
        return PromptTemplate(
            prompt_id=prompt_id,
            version=version,
            template=path.read_text(encoding="utf-8"),
        )

    def render(
        self,
        prompt_id: str,
        version: str = "v1",
        variables: dict[str, Any] | None = None,
    ) -> str:
        template = self.load(prompt_id, version)
        return render_prompt_template(template.template, variables or {})

    def _path(self, prompt_id: str, version: str) -> Path:
        return self.root / prompt_id / f"{version}.system.md"


def render_prompt_template(template: str, variables: dict[str, Any]) -> str:
    normalized = _VARIABLE_PATTERN.sub(r"{\1}", template)
    required = {
        field_name
        for _, field_name, _, _ in Formatter().parse(normalized)
        if field_name
    }
    missing = sorted(required - set(variables))
    if missing:
        raise ValueError(f"Missing prompt variables: {', '.join(missing)}")
    return normalized.format(**variables)
