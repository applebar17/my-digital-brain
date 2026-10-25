"""Local file-backed implementation of the prompt-template source contract."""

from pathlib import Path

from product.prompts.models import PromptReferenceDTO, PromptTemplateDTO


class FilePromptTemplateSource:
    """Load exact prompt versions from the product's versioned template directory."""

    def __init__(self, templates_root: Path) -> None:
        self.templates_root = templates_root.resolve()

    def load(self, reference: PromptReferenceDTO) -> PromptTemplateDTO:
        """Read `<prompt_id>/<version>.system.md` beneath the configured root.

        Dependencies:
            Uses only the injected root and exact `PromptReferenceDTO`; it does
            not select a latest version or fall back to another source.
        """
        template_path = (
            self.templates_root / reference.prompt_id / f"{reference.version}.system.md"
        ).resolve()
        if self.templates_root not in template_path.parents:
            raise ValueError(
                f"Prompt reference '{reference.prompt_id}:{reference.version}' escapes the "
                "configured template directory."
            )
        try:
            content = template_path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ValueError(
                f"Prompt template '{reference.prompt_id}:{reference.version}' was not found at "
                f"'{template_path}'."
            ) from error
        return PromptTemplateDTO(reference=reference, content=content)
