from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidateRelationshipDraftBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import INGESTION_RELATIONSHIP_EXTRACTION_TASK


class RelationshipExtractor(FocusedLLMExtractor):
    output_schema = CandidateRelationshipDraftBatch
    route_task = INGESTION_RELATIONSHIP_EXTRACTION_TASK
    supported_task_types = _task_set(
        ExtractionTaskType.RELATIONSHIP,
        ExtractionTaskType.LINK,
    )
