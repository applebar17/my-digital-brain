from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.protocols import ModelRouter, StructuredLLMProvider
from my_digital_brain.ai.schemas import AIRequestContext, StructuredGenerationRequest
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.ingestion.contracts import (
    CandidateOutput,
    ExtractionTask,
    IngestionContextPackage,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enrichment import enrich_candidate_batch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.prompt_builders import (
    IngestionPromptBuilder,
    system_prompt_with_runtime_context,
)


class FocusedLLMExtractor:
    output_schema: type[BaseModel]
    supported_task_types: frozenset[ExtractionTaskType]
    route_task: str

    def __init__(
        self,
        provider: StructuredLLMProvider,
        *,
        router: ModelRouter | None = None,
        prompt_builder: IngestionPromptBuilder | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.router = router
        self.prompt_builder = prompt_builder or IngestionPromptBuilder()
        self.model = model

    def supports(self, task: ExtractionTask) -> bool:
        return ExtractionTaskType(task.task_type) in self.supported_task_types

    @traceable(name="Focused Extraction", run_type="parser")
    def extract(
        self,
        source: SourceRecordRef,
        task: ExtractionTask,
        context: IngestionContextPackage,
    ) -> Sequence[CandidateOutput]:
        parsed = self._generate(source, task, context)
        return enrich_candidate_batch(parsed, source, task)

    @traceable(name="Focused Extraction Structured Call", run_type="parser")
    def _generate(
        self,
        source: SourceRecordRef,
        task: ExtractionTask,
        context: IngestionContextPackage,
    ) -> BaseModel:
        request_context = AIRequestContext(
            purpose=self.route_task,
            source_id=source.source_id,
            schema_id=self.output_schema.__name__,
            metadata={"task_id": task.task_id, "task_type": str(task.task_type)},
        )
        route = self.router.route(self.route_task, request_context) if self.router else None
        result = self.provider.generate_structured(
            StructuredGenerationRequest(
                schema=self.output_schema,
                system_prompt=system_prompt_with_runtime_context(
                    self.prompt_builder.extractor_system_prompt,
                    source,
                ),
                input_message=self.prompt_builder.extraction_input(source, task, context),
                model=self.model or (route.model if route else None),
                context=request_context,
                metadata={"route": route.model_dump(mode="json")} if route else {},
            ),
        )
        return result.parsed


def _task_set(*task_types: ExtractionTaskType) -> frozenset[ExtractionTaskType]:
    return frozenset(task_types)
