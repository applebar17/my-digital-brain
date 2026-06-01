from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidateEntityBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import INGESTION_ENTITY_EXTRACTION_TASK


class EntityExtractor(FocusedLLMExtractor):
    output_schema = CandidateEntityBatch
    route_task = INGESTION_ENTITY_EXTRACTION_TASK
    supported_task_types = _task_set(
        ExtractionTaskType.PERSON,
        ExtractionTaskType.PLACE,
        ExtractionTaskType.EVENT,
        ExtractionTaskType.ORGANIZATION,
        ExtractionTaskType.OBJECT,
        ExtractionTaskType.ANIMAL,
        ExtractionTaskType.SOCIAL_CIRCLE,
        ExtractionTaskType.TOPIC,
    )
