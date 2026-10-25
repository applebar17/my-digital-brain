from pathlib import Path

import pytest

from product.prompts import (
    FilePromptTemplateSource,
    PromptReferenceDTO,
    PromptRenderContextDTO,
    PromptRenderer,
    PromptService,
)


def _write_template(root: Path, prompt_id: str, version: str, content: str) -> None:
    template_directory = root / prompt_id
    template_directory.mkdir(parents=True)
    (template_directory / f"{version}.system.md").write_text(content, encoding="utf-8")


def test_prompt_service_loads_exact_version_and_renders_named_values(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "sample",
        "v2",
        "Use this context:\n{{ context }}\nLiteral object: {name}.",
    )
    service = PromptService(FilePromptTemplateSource(tmp_path), PromptRenderer())

    rendered = service.render(
        PromptReferenceDTO(prompt_id="sample", version="v2"),
        PromptRenderContextDTO(values={"context": "Known person: Amos."}),
    )

    assert rendered.text == "Use this context:\nKnown person: Amos.\nLiteral object: {name}."
    assert rendered.snapshot.prompt_id == "sample"
    assert rendered.snapshot.version == "v2"
    assert rendered.snapshot.template_checksum != rendered.snapshot.rendered_checksum


def test_prompt_service_rejects_missing_template_slot_before_an_llm_call(tmp_path: Path) -> None:
    _write_template(tmp_path, "sample", "v1", "Context: {{ required_context }}")
    service = PromptService(FilePromptTemplateSource(tmp_path), PromptRenderer())

    with pytest.raises(ValueError, match="required_context"):
        service.render(
            PromptReferenceDTO(prompt_id="sample", version="v1"),
            PromptRenderContextDTO(),
        )
