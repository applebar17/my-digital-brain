from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidateRelationshipContextBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import (
    INGESTION_RELATIONSHIP_CONTEXT_EXTRACTION_TASK,
)


class RelationshipContextExtractor(FocusedLLMExtractor):
    output_schema = CandidateRelationshipContextBatch
    route_task = INGESTION_RELATIONSHIP_CONTEXT_EXTRACTION_TASK
    supported_task_types = _task_set(
        ExtractionTaskType.RELATIONSHIP_CONTEXT,
        ExtractionTaskType.RELATIONSHIP_STATE,
    )
