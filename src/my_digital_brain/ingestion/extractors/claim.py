from __future__ import annotations

from my_digital_brain.ingestion.contracts import CandidateClaimDraftBatch
from my_digital_brain.ingestion.enums import ExtractionTaskType
from my_digital_brain.ingestion.extractors.base import FocusedLLMExtractor, _task_set
from my_digital_brain.ingestion.prompt_builders import INGESTION_CLAIM_EXTRACTION_TASK


class ClaimExtractor(FocusedLLMExtractor):
    output_schema = CandidateClaimDraftBatch
    route_task = INGESTION_CLAIM_EXTRACTION_TASK
    supported_task_types = _task_set(ExtractionTaskType.CLAIM)
