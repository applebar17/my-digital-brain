from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidateProfileMemoryBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import INGESTION_PROFILE_MEMORY_EXTRACTION_TASK


class ProfileMemoryExtractor(FocusedLLMExtractor):
    """Focused extractor for durable, provenance-backed owner profile proposals."""

    output_schema = CandidateProfileMemoryBatch
    route_task = INGESTION_PROFILE_MEMORY_EXTRACTION_TASK
    supported_task_types = _task_set(ExtractionTaskType.PROFILE_MEMORY)
