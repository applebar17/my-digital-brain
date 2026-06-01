from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.protocols import ModelRouter, StructuredLLMProvider
from my_digital_brain.ai.schemas import AIRequestContext, StructuredGenerationRequest
from my_digital_brain.ingestion.contracts import (
    ExtractionPlan,
    IngestionContextPackage,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.prompt_builders import (
    INGESTION_MENTION_SCAN_TASK,
    INGESTION_PLANNING_TASK,
    IngestionPromptBuilder,
)

GRAPH_ALIAS_PATTERN = re.compile(r"^(NODE|REL|CLAIM|SOURCE|RELCTX)_[0-9]{3,6}$")


class LLMMentionScanner:
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

    def scan(self, source: SourceRecordRef) -> MentionScan:
        parsed = _structured_call(
            provider=self.provider,
            output_schema=MentionScan,
            system_prompt=self.prompt_builder.mention_scan_system_prompt,
            input_message=self.prompt_builder.mention_scan_input(source),
            source=source,
            purpose=INGESTION_MENTION_SCAN_TASK,
            router=self.router,
            model=self.model,
        )
        mention_scan = MentionScan.model_validate(parsed)
        if mention_scan.source_id != source.source_id:
            raise IngestionValidationError(
                "Mention scan returned source_id "
                f"'{mention_scan.source_id}' but expected '{source.source_id}'."
            )
        return mention_scan


class LLMIngestionPlanner:
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

    def plan(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        parsed = _structured_call(
            provider=self.provider,
            output_schema=ExtractionPlan,
            system_prompt=self.prompt_builder.planner_system_prompt,
            input_message=self.prompt_builder.planner_input(source, mention_scan, context),
            source=source,
            purpose=INGESTION_PLANNING_TASK,
            router=self.router,
            model=self.model,
        )
        plan = ExtractionPlan.model_validate(parsed)
        if plan.source_id != source.source_id:
            raise IngestionValidationError(
                f"Extraction plan returned source_id '{plan.source_id}' "
                f"but expected '{source.source_id}'."
            )
        self._validate_plan_aliases(plan, context)
        return plan

    def _validate_plan_aliases(
        self,
        plan: ExtractionPlan,
        context: IngestionContextPackage,
    ) -> None:
        known_aliases = set(context.aliases)
        unknown_aliases: list[str] = []
        for task in plan.tasks:
            refs = [task.target_ref, *task.required_context_refs]
            for ref in refs:
                if ref and _is_graph_alias(ref) and ref not in known_aliases:
                    unknown_aliases.append(ref)
        if plan.clarification:
            for ref in plan.clarification.target_refs:
                if _is_graph_alias(ref) and ref not in known_aliases:
                    unknown_aliases.append(ref)
        if unknown_aliases:
            raise IngestionValidationError(
                "Extraction plan referenced graph aliases that were not present "
                f"in compact context: {sorted(set(unknown_aliases))}."
            )


def _structured_call(
    *,
    provider: StructuredLLMProvider,
    output_schema: type[BaseModel],
    system_prompt: str,
    input_message: dict[str, Any],
    source: SourceRecordRef,
    purpose: str,
    router: ModelRouter | None,
    model: str | None,
) -> BaseModel:
    context = AIRequestContext(
        purpose=purpose,
        source_id=source.source_id,
        schema_id=output_schema.__name__,
        metadata={"source_type": str(source.source_type), "channel": str(source.channel)},
    )
    route = router.route(purpose, context) if router else None
    result = provider.generate_structured(
        StructuredGenerationRequest(
            schema=output_schema,
            system_prompt=system_prompt,
            input_message=input_message,
            model=model or (route.model if route else None),
            context=context,
            metadata={"route": route.model_dump(mode="json")} if route else {},
        ),
    )
    return result.parsed


def _is_graph_alias(ref: str) -> bool:
    return bool(GRAPH_ALIAS_PATTERN.match(ref))
