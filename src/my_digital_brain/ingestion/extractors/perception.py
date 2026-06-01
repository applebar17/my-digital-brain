from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidatePerceptionBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import INGESTION_PERCEPTION_EXTRACTION_TASK


class PerceptionExtractor(FocusedLLMExtractor):
    output_schema = CandidatePerceptionBatch
    route_task = INGESTION_PERCEPTION_EXTRACTION_TASK
    supported_task_types = _task_set(ExtractionTaskType.PERCEPTION)
