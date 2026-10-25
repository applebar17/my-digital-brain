"""Literal named-slot renderer for versioned prompt templates."""

import re
from hashlib import sha256

from product.prompts.models import (
    PromptRenderContextDTO,
    PromptSnapshotDTO,
    PromptTemplateDTO,
    RenderedPromptDTO,
)

_PROMPT_SLOT = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


class PromptRenderer:
    """Render declared `{{ name }}` slots without evaluating expressions."""

    def render(
        self,
        template: PromptTemplateDTO,
        context: PromptRenderContextDTO,
    ) -> RenderedPromptDTO:
        """Substitute named strings and produce reproducible prompt checksums.

        Missing slots fail before an LLM call. Unreferenced context values are
        permitted so a shared context builder can serve compatible templates.
        Braces that do not match the named-slot syntax remain literal text.
        """
        required_names = set(_PROMPT_SLOT.findall(template.content))
        missing_names = sorted(required_names - context.values.keys())
        if missing_names:
            missing = ", ".join(missing_names)
            raise ValueError(
                f"Prompt '{template.reference.prompt_id}:{template.reference.version}' is missing "
                f"render values for: {missing}."
            )

        rendered = _PROMPT_SLOT.sub(lambda match: context.values[match.group(1)], template.content)
        reference = template.reference
        return RenderedPromptDTO(
            text=rendered,
            snapshot=PromptSnapshotDTO(
                prompt_id=reference.prompt_id,
                version=reference.version,
                template_checksum=self._checksum(template.content),
                rendered_checksum=self._checksum(rendered),
            ),
        )

    @staticmethod
    def _checksum(content: str) -> str:
        """Return the lowercase SHA-256 identity of UTF-8 prompt text."""
        return sha256(content.encode("utf-8")).hexdigest()
