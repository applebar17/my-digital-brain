"""Retry and provider-compatibility helpers for GenAI calls."""

from __future__ import annotations

import inspect
import time
from typing import Any

from my_digital_brain.ai.context import is_context_length_error
from my_digital_brain.debug import (
    AIFlowTraceSection,
    record_ai_flow_event,
    record_openai_payload,
    record_openai_response,
)

from .compatibility import apply_chat_completion_compatibility


class GenAIRetryMixin:
    def _call_with_retries(self, params: dict[str, Any]):
        params = self._prepare_chat_completion_params(params)
        adjusted_for_temperature = False
        adjusted_for_max_tokens = False
        adjusted_for_context = False
        for attempt in range(1, self.max_retries + 1):
            try:
                self._ensure_context_budget(params)
                record_openai_payload(params, metadata={"attempt": attempt})
                response = self.client.chat.completions.create(**params)
                record_openai_response(response, metadata={"attempt": attempt})
                return response
            except Exception as exc:  # pragma: no cover
                _record_openai_error(exc, attempt=attempt)
                if not adjusted_for_temperature and self._should_retry_without_temperature(
                    exc, params
                ):
                    adjusted_for_temperature = True
                    params = self._drop_temperature(params)
                    self.logger.warning(
                        "OpenAI model rejected explicit temperature; retrying without temperature."
                    )
                    continue
                if not adjusted_for_max_tokens and self._should_retry_with_max_completion_tokens(
                    exc, params
                ):
                    adjusted_for_max_tokens = True
                    params = self._replace_max_tokens(params)
                    self.logger.warning(
                        "OpenAI model rejected max_tokens; retrying with max_completion_tokens."
                    )
                    continue
                if not adjusted_for_max_tokens and self._should_retry_with_max_tokens(exc, params):
                    adjusted_for_max_tokens = True
                    params = self._replace_max_completion_tokens(params)
                    self.logger.warning(
                        "OpenAI SDK rejected max_completion_tokens; retrying with max_tokens."
                    )
                    continue
                if not adjusted_for_context and self._should_retry_after_context_compaction(
                    exc, params
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

    def _should_retry_with_max_tokens(
        self,
        exc: Exception,
        params: dict[str, Any],
    ) -> bool:
        if "max_completion_tokens" not in params:
            return False

        message = str(exc).lower()
        if "max_completion_tokens" not in message:
            return False

        unsupported_markers = (
            "unexpected keyword argument",
            "unsupported_parameter",
            "unrecognized request argument",
            "not supported",
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

    def _replace_max_completion_tokens(self, params: dict[str, Any]) -> dict[str, Any]:
        updated = dict(params)
        max_completion_tokens = updated.pop("max_completion_tokens", None)
        if max_completion_tokens is not None and "max_tokens" not in updated:
            updated["max_tokens"] = max_completion_tokens
        return updated

    def _prepare_chat_completion_params(self, params: dict[str, Any]) -> dict[str, Any]:
        updated = apply_chat_completion_compatibility(params)
        if "max_completion_tokens" in updated and not self._chat_completion_create_accepts(
            "max_completion_tokens"
        ):
            return self._replace_max_completion_tokens(updated)
        return updated

    def _chat_completion_create_accepts(self, parameter_name: str) -> bool:
        try:
            signature = inspect.signature(self.client.chat.completions.create)
        except (AttributeError, TypeError, ValueError):
            return True
        parameters = signature.parameters
        if parameter_name in parameters:
            return True
        return any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        )

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


def _record_openai_error(exc: Exception, *, attempt: int) -> None:
    record_ai_flow_event(
        title="OpenAI Error",
        call_kind="openai_error",
        status="error",
        sections=[
            AIFlowTraceSection(
                title="ERROR / DIAGNOSTICS",
                content=f"{exc.__class__.__name__}: {exc}",
                content_type="text",
            )
        ],
        metadata={"attempt": attempt, "error_type": exc.__class__.__name__},
    )
