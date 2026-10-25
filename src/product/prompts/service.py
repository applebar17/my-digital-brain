"""Prompt resolution service composed from an injected source and renderer."""

from product.prompts.models import (
    PromptReferenceDTO,
    PromptRenderContextDTO,
    PromptTemplateSource,
    RenderedPromptDTO,
)
from product.prompts.renderer import PromptRenderer


class PromptService:
    """Resolve and render an exact prompt without owning source configuration."""

    def __init__(self, source: PromptTemplateSource, renderer: PromptRenderer) -> None:
        self.source = source
        self.renderer = renderer

    def render(
        self,
        reference: PromptReferenceDTO,
        context: PromptRenderContextDTO,
    ) -> RenderedPromptDTO:
        """Load and render the exact reference through configured collaborators.

        Dependencies:
            The injected source decides where templates live. `PromptRenderer`
            performs deterministic literal substitution and computes identity.
        """
        return self.renderer.render(self.source.load(reference), context)
