"""Retry and provider-compatibility helpers for GenAI calls."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.context import is_context_length_error
from my_digital_brain.ai.structured_schema import strict_response_format
from my_digital_brain.ai.tracing import traceable
from .compatibility import apply_chat_completion_compatibility


class GenAIRetryMixin:
    def _call_with_retries(self, params: dict[str, Any]):
        params = apply_chat_completion_compatibility(params)
        adjusted_for_temperature = False
        adjusted_for_max_tokens = False
        adjusted_for_context = False
        for attempt in range(1, self.max_retries + 1):
            try:
                self._ensure_context_budget(params)
                return self.client.chat.completions.create(**params)
            except Exception as exc:  # pragma: no cover
                if (
                    not adjusted_for_temperature
                    and self._should_retry_without_temperature(exc, params)
                ):
                    adjusted_for_temperature = True
                    params = self._drop_temperature(params)
                    self.logger.warning(
                        "OpenAI model rejected explicit temperature; retrying without temperature."
                    )
                    continue
                if (
                    not adjusted_for_max_tokens
                    and self._should_retry_with_max_completion_tokens(exc, params)
                ):
                    adjusted_for_max_tokens = True
                    params = self._replace_max_tokens(params)
                    self.logger.warning(
                        "OpenAI model rejected max_tokens; retrying with max_completion_tokens."
                    )
                    continue
                if (
                    not adjusted_for_context
                    and self._should_retry_after_context_compaction(exc, params)
                ):
                    adjusted_for_context = True
                    self._record_context_limit_from_error(exc, params.get("model"))
                    compacted = self._force_context_compaction(params)
                    self.logger.warning(
                        "OpenAI call exceeded context limit; compacted=%s and retrying once.",
                        compacted,
                    )
                    continue
                if not self._is_retryable_error(exc) or attempt == self.max_retries:
                    raise
                delay = self.retry_backoff_seconds * attempt
                self.logger.warning(
                    "OpenAI call failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    self.max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise RuntimeError("Retries exhausted for OpenAI call.")

    @traceable(name="Structured LLM Call", run_type="parser")
    def _call_structured_response_with_retries(self, params: dict[str, Any]):
        params = self._normalize_structured_response_format(params)
        params = apply_chat_completion_compatibility(params)
        adjusted_for_temperature = False
        adjusted_for_max_tokens = False
        adjusted_for_context = False
        for attempt in range(1, self.max_retries + 1):
            try:
                self._ensure_context_budget(params)
                if _is_json_schema_response_format(params.get("response_format")):
                    return self.client.chat.completions.create(**params)
                if hasattr(self.client, "chat") and hasattr(
                    self.client.chat.completions, "parse"
                ):
                    return self.client.chat.completions.parse(**params)
                if hasattr(self.client, "beta"):
                    return self.client.beta.chat.completions.parse(**params)
                fallback_params = dict(params)
                fallback_params.pop("response_format", None)
                return self.client.chat.completions.create(**fallback_params)
            except Exception as exc:  # pragma: no cover
                if (
                    not adjusted_for_temperature
                    and self._should_retry_without_temperature(exc, params)
                ):
                    adjusted_for_temperature = True
                    params = self._drop_temperature(params)
                    self.logger.warning(
                        "OpenAI model rejected explicit temperature; retrying "
                        "structured call without temperature."
                    )
                    continue
                if (
                    not adjusted_for_max_tokens
                    and self._should_retry_with_max_completion_tokens(exc, params)
                ):
                    adjusted_for_max_tokens = True
                    params = self._replace_max_tokens(params)
                    self.logger.warning(
                        "OpenAI model rejected max_tokens; retrying structured "
                        "call with max_completion_tokens."
                    )
                    continue
                if (
                    not adjusted_for_context
                    and self._should_retry_after_context_compaction(exc, params)
                ):
                    adjusted_for_context = True
                    self._record_context_limit_from_error(exc, params.get("model"))
                    compacted = self._force_context_compaction(params)
                    self.logger.warning(
                        "OpenAI structured call exceeded context limit; compacted=%s "
                        "and retrying once.",
                        compacted,
                    )
                    continue
                if not self._is_retryable_error(exc) or attempt == self.max_retries:
                    raise
                delay = self.retry_backoff_seconds * attempt
                self.logger.warning(
                    "OpenAI structured call failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    self.max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise RuntimeError("Retries exhausted for structured OpenAI call.")

    def _call_structured_with_retries(
        self,
        schema: type[BaseModel],
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float | None,
        max_tokens: int | None,
        max_completion_tokens: int | None = None,
    ) -> BaseModel:
        adjusted_for_temperature = False
        adjusted_for_max_tokens = False
        adjusted_for_context = False
        for attempt in range(1, self.max_retries + 1):
            try:
                params_for_budget: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                }
                if max_tokens is not None:
                    params_for_budget["max_tokens"] = max_tokens
                if max_completion_tokens is not None:
                    params_for_budget["max_completion_tokens"] = max_completion_tokens
                self._ensure_context_budget(params_for_budget)
                messages = params_for_budget["messages"]
                return self._call_structured_once(
                    schema,
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_completion_tokens=max_completion_tokens,
                )
            except Exception as exc:  # pragma: no cover
                if (
                    not adjusted_for_temperature
                    and self._should_retry_without_temperature(
                        exc,
                        {"model": model, "temperature": temperature},
                    )
                ):
                    adjusted_for_temperature = True
                    temperature = None
                    self.logger.warning(
                        "OpenAI model rejected explicit temperature; retrying "
                        "structured parse call without temperature."
                    )
                    continue
                if (
                    not adjusted_for_max_tokens
                    and self._should_retry_with_max_completion_tokens(
                        exc,
                        {"model": model, "max_tokens": max_tokens},
                    )
                ):
                    adjusted_for_max_tokens = True
                    self.logger.warning(
                        "OpenAI model rejected max_tokens; retrying structured "
                        "parse call with max_completion_tokens."
                    )
                    max_completion_tokens = (
                        None if max_tokens is None else int(max_tokens)
                    )
                    max_tokens = None
                    continue
                if not adjusted_for_context and is_context_length_error(exc):
                    adjusted_for_context = True
                    self._record_context_limit_from_error(exc, model)
                    params_for_budget = {
                        "model": model,
                        "messages": messages,
                    }
                    if max_tokens is not None:
                        params_for_budget["max_tokens"] = max_tokens
                    if max_completion_tokens is not None:
                        params_for_budget["max_completion_tokens"] = max_completion_tokens
                    compacted = self._force_context_compaction(params_for_budget)
                    messages = params_for_budget["messages"]
                    self.logger.warning(
                        "OpenAI structured parse call exceeded context limit; "
                        "compacted=%s and retrying once.",
                        compacted,
                    )
                    continue
                if not self._is_retryable_error(exc) or attempt == self.max_retries:
                    raise
                delay = self.retry_backoff_seconds * attempt
                self.logger.warning(
                    "OpenAI structured call failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    self.max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("Retries exhausted for structured OpenAI call.")

    @traceable(name="Structurization", run_type="parser")
    def _call_structured_once(
        self,
        schema: type[BaseModel],
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float | None,
        max_tokens: int | None,
        max_completion_tokens: int | None = None,
    ) -> BaseModel:
        params = {
            "model": model,
            "messages": messages,
            "response_format": strict_response_format(schema),
        }
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if max_completion_tokens is not None:
            params["max_completion_tokens"] = max_completion_tokens
        params = apply_chat_completion_compatibility(params)
        response = self.client.chat.completions.create(**params)
        content = response.choices[0].message.content
        if not content:
            finish_reason = _response_finish_reason(response)
            raise ValueError(
                "Structured generation returned empty content for schema "
                f"{schema.__name__}. finish_reason={finish_reason or 'unknown'}"
            )
        return schema.model_validate_json(content)

    def _normalize_structured_response_format(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        response_format = params.get("response_format")
        if (
            isinstance(response_format, type)
            and issubclass(response_format, BaseModel)
        ):
            updated = dict(params)
            updated["response_format"] = strict_response_format(response_format)
            return updated
        return params

    def _should_retry_without_temperature(
        self,
        exc: Exception,
        params: dict[str, Any],
    ) -> bool:
        if "temperature" not in params:
            return False

        message = str(exc).lower()
        if "temperature" not in message:
            return False

        unsupported_markers = (
            "does not support",
            "only the default",
            "unsupported_value",
        )
        return any(marker in message for marker in unsupported_markers)

    def _drop_temperature(self, params: dict[str, Any]) -> dict[str, Any]:
        updated = dict(params)
        updated.pop("temperature", None)
        return updated

    def _should_retry_with_max_completion_tokens(
        self,
        exc: Exception,
        params: dict[str, Any],
    ) -> bool:
        if "max_tokens" not in params:
            return False

        message = str(exc).lower()
        if "max_tokens" not in message:
            return False

        unsupported_markers = (
            "not supported with this model",
            "use 'max_completion_tokens' instead",
            "unsupported_parameter",
        )
        return any(marker in message for marker in unsupported_markers)

    def _should_retry_after_context_compaction(
        self,
        exc: Exception,
        params: dict[str, Any],
    ) -> bool:
        if not is_context_length_error(exc):
            return False
        messages = params.get("messages")
        return isinstance(messages, list) and bool(messages)

    def _replace_max_tokens(self, params: dict[str, Any]) -> dict[str, Any]:
        updated = dict(params)
        max_tokens = updated.pop("max_tokens", None)
        if max_tokens is not None:
            updated["max_completion_tokens"] = max_tokens
        return updated

    def _is_retryable_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        retry_markers = (
            "rate limit",
            "timeout",
            "temporarily unavailable",
            "server error",
            "502",
            "503",
            "504",
        )
        return any(marker in message for marker in retry_markers)


def _is_json_schema_response_format(response_format: Any) -> bool:
    return (
        isinstance(response_format, dict)
        and response_format.get("type") == "json_schema"
    )


def _response_finish_reason(response: Any) -> str | None:
    try:
        choice = response.choices[0]
    except (AttributeError, IndexError, TypeError):
        return None
    if isinstance(choice, dict):
        value = choice.get("finish_reason")
    else:
        value = getattr(choice, "finish_reason", None)
    return str(value) if value is not None else None
