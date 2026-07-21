"""OpenAI/Azure Chat Completions transport and media client."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from my_digital_brain.ai.context import ContextBudgetResolver, GenAIContextManager
from my_digital_brain.ai.tokenizer import TokenCounter
from my_digital_brain.ai.tracing import traceable, wrap_openai_client

from .context_ops import GenAIContextMixin
from .retrying import GenAIRetryMixin
from .settings import GenAISettings, get_genai_settings


class GenAIClient(GenAIRetryMixin, GenAIContextMixin):
    """Execute one provider request; session orchestration lives above this class."""

    def __init__(
        self,
        settings: GenAISettings | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings or get_genai_settings()
        self.logger = logger or logging.getLogger(__name__)
        self.client = self._make_client()
        self.token_counter = TokenCounter()
        self.context_manager = self._build_context_manager()
        self.max_context_tokens = self.settings.context_fallback_tokens
        self.output_reserve_tokens = self.settings.output_reserve_tokens
        self.max_retries = 3
        self.retry_backoff_seconds = 1.5
        self._log_configuration()

    @traceable(name="Chat Completion Transport", run_type="llm")
    def complete_chat(self, params: dict[str, Any]) -> Any:
        """Perform one Chat Completions request without executing tools."""
        prepared = self._prepare_chat_completion_params(dict(params))
        self._ensure_context_budget(prepared)
        return self._call_with_retries(prepared)

    @traceable(name="Embed Texts", run_type="embedding")
    def embed(
        self,
        texts: Iterable[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        params: dict[str, Any] = {
            "model": model or self._default_embed_model(),
            "input": list(texts),
        }
        dimensions = dimensions or getattr(self.settings, "embed_dimensions", None)
        if dimensions:
            params["dimensions"] = dimensions
        response = self.client.embeddings.create(**params)
        return [item.embedding for item in response.data]

    @traceable(name="Transcribe Audio", run_type="tool")
    def transcribe_audio(
        self,
        audio_path: str | Path,
        *,
        model: str | None = None,
        language: str | None = None,
        prompt: str | None = None,
        response_format: str = "verbose_json",
    ) -> Any:
        params: dict[str, Any] = {
            "model": model or self._default_transcription_model(),
            "response_format": response_format,
        }
        if language:
            params["language"] = language
        if prompt:
            params["prompt"] = prompt
        with Path(audio_path).open("rb") as audio_file:
            params["file"] = audio_file
            return self.client.audio.transcriptions.create(**params)

    def _default_chat_model(self) -> str:
        return self.settings.chat_model_default or "gpt-4o-mini"

    def chat_model_for(self, purpose: str | None = None) -> str:
        key = (purpose or "default").strip().lower()
        default_model = self._default_chat_model()
        if key in {"strategic", "strategy", "critical", "smart"}:
            return self.settings.chat_model_smart or default_model
        if key in {"reasoning", "reason"}:
            return self.settings.chat_model_reasoning or default_model
        return default_model

    def _default_embed_model(self) -> str:
        if self.settings.is_azure:
            return self.settings.azure_openai_embed_deployment or "text-embedding-3-small"
        return self.settings.openai_embed_model

    def _default_transcription_model(self) -> str:
        if self.settings.is_azure:
            return (
                self.settings.azure_openai_transcription_deployment
                or self.settings.openai_transcription_model
            )
        return self.settings.openai_transcription_model

    def _make_client(self):
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError("openai package is required for GenAIClient.") from exc

        if self.settings.is_azure:
            if not self.settings.azure_openai_endpoint or not self.settings.azure_openai_api_key:
                raise RuntimeError("Azure OpenAI settings are missing.")
            client = openai.AzureOpenAI(
                api_key=self.settings.azure_openai_api_key,
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_version=self.settings.azure_openai_api_version,
            )
            return wrap_openai_client(client)

        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing.")
        return wrap_openai_client(openai.OpenAI(api_key=self.settings.openai_api_key))

    def _build_context_manager(self) -> GenAIContextManager:
        tier_context_tokens = {
            key: value
            for key, value in {
                "default": self.settings.context_tokens_default,
                "smart": self.settings.context_tokens_smart,
                "reasoning": self.settings.context_tokens_reasoning,
            }.items()
            if value is not None
        }
        resolver = ContextBudgetResolver(
            tier_context_tokens=tier_context_tokens,
            model_context_tokens=self.settings.context_tokens_by_model,
            fallback_tokens=self.settings.context_fallback_tokens,
        )
        return GenAIContextManager(
            resolver=resolver,
            token_counter=self.token_counter,
            guard_ratio=self.settings.context_guard_ratio,
            output_reserve_tokens=self.settings.output_reserve_tokens,
            recent_messages=self.settings.context_recent_messages,
            summary_max_tokens=self.settings.context_summary_max_tokens,
            logger=self.logger,
        )

    def _log_configuration(self) -> None:
        self.logger.debug(
            "GenAI client init: provider=%s chat_default=%s chat_smart=%s "
            "chat_reasoning=%s embed_model=%s transcription_model=%s",
            "azure_openai" if self.settings.is_azure else "openai",
            self.settings.chat_model_default or "unset",
            self.settings.chat_model_smart or "unset",
            self.settings.chat_model_reasoning or "unset",
            self.settings.openai_embed_model or "unset",
            self.settings.openai_transcription_model or "unset",
        )
