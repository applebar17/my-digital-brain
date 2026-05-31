"""Azure OpenAI provider adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .openai import OpenAIProvider, _response_request_id
from ..schemas import ProviderCallMetadata


class AzureOpenAIProvider(OpenAIProvider):
    provider_name = "azure_openai"

    def _metadata(
        self,
        *,
        model: str | None,
        started_at: datetime,
        latency_ms: int,
        raw_response: Any | None = None,
    ) -> ProviderCallMetadata:
        return ProviderCallMetadata(
            provider=self.provider_name,
            model=model,
            deployment=model,
            request_id=_response_request_id(raw_response),
            started_at=started_at,
            ended_at=datetime.now(started_at.tzinfo),
            latency_ms=latency_ms,
        )
