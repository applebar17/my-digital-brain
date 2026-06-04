from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidateMetadataPatchDraftBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import INGESTION_METADATA_PATCH_EXTRACTION_TASK


class MetadataPatchExtractor(FocusedLLMExtractor):
    output_schema = CandidateMetadataPatchDraftBatch
    route_task = INGESTION_METADATA_PATCH_EXTRACTION_TASK
    supported_task_types = _task_set(ExtractionTaskType.METADATA_PATCH)
