"""Deterministic model routing for AI provider calls."""

from __future__ import annotations

from dataclasses import dataclass, field

from .client.settings import GenAISettings, get_genai_settings
from .schemas import AIRequestContext, ModelRoute


DEFAULT_ROUTE_TASK = "default_chat"
STRUCTURED_EXTRACTION_TASK = "structured_extraction"
SUMMARIZATION_TASK = "summarization"
EMBEDDING_TASK = "embedding"
SPEECH_TO_TEXT_TASK = "speech_to_text"
AGENTIC_SMART_TASKS = {
    "memory_query",
    "correction_intake",
    "memory_ingestion_planning",
}
AGENTIC_REASONING_TASKS = {"contradiction_review"}


@dataclass(slots=True)
class StaticModelRouter:
    settings: GenAISettings = field(default_factory=get_genai_settings)
    provider: str | None = None
    task_overrides: dict[str, ModelRoute] = field(default_factory=dict)

    def route(
        self,
        task: str,
        context: AIRequestContext | None = None,
    ) -> ModelRoute:
        normalized_task = _normalize_task(task)
        if normalized_task in self.task_overrides:
            return self.task_overrides[normalized_task]
        provider = self.provider or (
            "azure_openai" if self.settings.is_azure else "openai"
        )
        return self._default_route(normalized_task, provider=provider, context=context)

    def _default_route(
        self,
        task: str,
        *,
        provider: str,
        context: AIRequestContext | None,
    ) -> ModelRoute:
        if task == STRUCTURED_EXTRACTION_TASK or task in AGENTIC_SMART_TASKS:
            model = self.settings.chat_model_smart or self.settings.chat_model_default
        elif task in AGENTIC_REASONING_TASKS:
            model = self.settings.chat_model_reasoning or self.settings.chat_model_default
        elif task == SUMMARIZATION_TASK:
            model = self.settings.chat_model_default
        elif task == EMBEDDING_TASK:
            model = self._embedding_model(provider)
        elif task == SPEECH_TO_TEXT_TASK:
            model = self._transcription_model(provider)
        else:
            model = self.settings.chat_model_default
        return ModelRoute(
            task=task,
            provider=provider,
            model=model,
            deployment=self._deployment_for_task(task, provider=provider),
            options={"purpose": context.purpose} if context and context.purpose else {},
        )

    def _embedding_model(self, provider: str) -> str:
        if provider == "azure_openai" and self.settings.azure_openai_embed_deployment:
            return self.settings.azure_openai_embed_deployment
        return self.settings.openai_embed_model

    def _transcription_model(self, provider: str) -> str:
        if (
            provider == "azure_openai"
            and self.settings.azure_openai_transcription_deployment
        ):
            return self.settings.azure_openai_transcription_deployment
        return self.settings.openai_transcription_model

    def _deployment_for_task(self, task: str, *, provider: str) -> str | None:
        if provider != "azure_openai":
            return None
        if task == EMBEDDING_TASK:
            return self.settings.azure_openai_embed_deployment
        if task == SPEECH_TO_TEXT_TASK:
            return self.settings.azure_openai_transcription_deployment
        return None


def _normalize_task(task: str) -> str:
    normalized = str(task or "").strip().lower()
    return normalized or DEFAULT_ROUTE_TASK
