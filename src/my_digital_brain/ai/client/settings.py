"""GenAI settings resolution from env and app configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

from my_digital_brain.ai.context import (
    DEFAULT_CONTEXT_FALLBACK_TOKENS,
    DEFAULT_CONTEXT_GUARD_RATIO,
    DEFAULT_CONTEXT_RECENT_MESSAGES,
    DEFAULT_CONTEXT_SUMMARY_MAX_TOKENS,
    DEFAULT_OUTPUT_RESERVE_TOKENS,
    parse_context_token_value,
    parse_context_tokens_by_model_json,
)


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_context_tokens(name: str) -> int | None:
    return parse_context_token_value(os.getenv(name))


def _env_context_tokens_default(name: str, default: int) -> int:
    parsed = parse_context_token_value(os.getenv(name))
    return parsed if parsed is not None else default


def _settings_context_tokens(value: str | None) -> int | None:
    return parse_context_token_value(value)


def _settings_context_tokens_default(value: str | None, default: int) -> int:
    parsed = parse_context_token_value(value)
    return parsed if parsed is not None else default


def _safe_int(value: Any, default: int) -> int:
    if value is None or not str(value).strip():
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def _safe_float(value: Any, default: float) -> float:
    if value is None or not str(value).strip():
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


@dataclass(slots=True)
class GenAISettings:
    openai_api_key: str | None = None
    openai_embed_model: str = "text-embedding-3-small"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    chat_model_default: str = "gpt-4o-mini"
    chat_model_smart: str = "gpt-4.1"
    chat_model_reasoning: str = "o4-mini"
    embed_dimensions: int | None = None
    context_tokens_default: int | None = None
    context_tokens_smart: int | None = None
    context_tokens_reasoning: int | None = None
    context_tokens_by_model: dict[str, int] = field(default_factory=dict)
    context_fallback_tokens: int = DEFAULT_CONTEXT_FALLBACK_TOKENS
    context_guard_ratio: float = DEFAULT_CONTEXT_GUARD_RATIO
    output_reserve_tokens: int = DEFAULT_OUTPUT_RESERVE_TOKENS
    context_recent_messages: int = DEFAULT_CONTEXT_RECENT_MESSAGES
    context_summary_max_tokens: int = DEFAULT_CONTEXT_SUMMARY_MAX_TOKENS
    is_azure: bool = False
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_embed_deployment: str | None = None
    azure_openai_transcription_deployment: str | None = None
    genai_tool_call_limit: int = 8
    genai_tool_call_timeout_seconds: float = 30.0


def get_genai_settings() -> GenAISettings:
    load_env_file()
    embed_dimensions_raw = os.getenv("OPENAI_EMBED_DIMENSIONS")
    embed_dimensions = None
    if embed_dimensions_raw and embed_dimensions_raw.strip():
        try:
            embed_dimensions = int(embed_dimensions_raw)
        except ValueError:
            embed_dimensions = None

    return GenAISettings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_embed_model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        openai_transcription_model=os.getenv(
            "OPENAI_TRANSCRIPTION_MODEL",
            "gpt-4o-mini-transcribe",
        ),
        chat_model_default=os.getenv("OPENAI_CHAT_MODEL_DEFAULT", "gpt-4o-mini"),
        chat_model_smart=os.getenv("OPENAI_CHAT_MODEL_SMART", "gpt-4.1"),
        chat_model_reasoning=os.getenv("OPENAI_CHAT_MODEL_REASONING", "o4-mini"),
        embed_dimensions=embed_dimensions,
        context_tokens_default=_env_context_tokens("GENAI_CONTEXT_TOKENS_DEFAULT"),
        context_tokens_smart=_env_context_tokens("GENAI_CONTEXT_TOKENS_SMART"),
        context_tokens_reasoning=_env_context_tokens("GENAI_CONTEXT_TOKENS_REASONING"),
        context_tokens_by_model=parse_context_tokens_by_model_json(
            os.getenv("GENAI_CONTEXT_TOKENS_BY_MODEL_JSON")
        ),
        context_fallback_tokens=_env_context_tokens_default(
            "GENAI_CONTEXT_FALLBACK_TOKENS",
            DEFAULT_CONTEXT_FALLBACK_TOKENS,
        ),
        context_guard_ratio=_env_float(
            "GENAI_CONTEXT_GUARD_RATIO",
            DEFAULT_CONTEXT_GUARD_RATIO,
        ),
        output_reserve_tokens=_env_int(
            "GENAI_OUTPUT_RESERVE_TOKENS",
            DEFAULT_OUTPUT_RESERVE_TOKENS,
        ),
        context_recent_messages=_env_int(
            "GENAI_CONTEXT_RECENT_MESSAGES",
            DEFAULT_CONTEXT_RECENT_MESSAGES,
        ),
        context_summary_max_tokens=_env_int(
            "GENAI_CONTEXT_SUMMARY_MAX_TOKENS",
            DEFAULT_CONTEXT_SUMMARY_MAX_TOKENS,
        ),
        is_azure=_env_bool("AZURE_OPENAI_ENABLED", False),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_openai_api_version=os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-10-21"
        ),
        azure_openai_embed_deployment=os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT"),
        azure_openai_transcription_deployment=os.getenv(
            "AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT"
        ),
        genai_tool_call_limit=_env_int("GENAI_TOOL_CALL_LIMIT", 8),
        genai_tool_call_timeout_seconds=_env_float(
            "GENAI_TOOL_CALL_TIMEOUT_SECONDS", 30.0
        ),
    )


def genai_settings_from_app_settings(settings: Any) -> GenAISettings:
    embed_dimensions = None
    raw_dimensions = str(getattr(settings, "openai_embed_dimensions", None) or "").strip()
    if raw_dimensions:
        try:
            embed_dimensions = int(raw_dimensions)
        except ValueError:
            embed_dimensions = None

    return GenAISettings(
        openai_api_key=getattr(settings, "openai_api_key", None),
        openai_embed_model=getattr(
            settings,
            "openai_embed_model",
            "text-embedding-3-small",
        ),
        openai_transcription_model=getattr(
            settings,
            "openai_transcription_model",
            "gpt-4o-mini-transcribe",
        ),
        chat_model_default=getattr(settings, "openai_chat_model_default", "gpt-4o-mini"),
        chat_model_smart=getattr(settings, "openai_chat_model_smart", "gpt-4.1"),
        chat_model_reasoning=getattr(settings, "openai_chat_model_reasoning", "o4-mini"),
        embed_dimensions=embed_dimensions,
        context_tokens_default=_settings_context_tokens(
            getattr(settings, "genai_context_tokens_default", None)
        ),
        context_tokens_smart=_settings_context_tokens(
            getattr(settings, "genai_context_tokens_smart", None)
        ),
        context_tokens_reasoning=_settings_context_tokens(
            getattr(settings, "genai_context_tokens_reasoning", None)
        ),
        context_tokens_by_model=parse_context_tokens_by_model_json(
            getattr(settings, "genai_context_tokens_by_model_json", None)
        ),
        context_fallback_tokens=_settings_context_tokens_default(
            getattr(settings, "genai_context_fallback_tokens", None),
            DEFAULT_CONTEXT_FALLBACK_TOKENS,
        ),
        context_guard_ratio=_safe_float(
            getattr(settings, "genai_context_guard_ratio", None),
            DEFAULT_CONTEXT_GUARD_RATIO,
        ),
        output_reserve_tokens=_safe_int(
            getattr(settings, "genai_output_reserve_tokens", None),
            DEFAULT_OUTPUT_RESERVE_TOKENS,
        ),
        context_recent_messages=_safe_int(
            getattr(settings, "genai_context_recent_messages", None),
            DEFAULT_CONTEXT_RECENT_MESSAGES,
        ),
        context_summary_max_tokens=_safe_int(
            getattr(settings, "genai_context_summary_max_tokens", None),
            DEFAULT_CONTEXT_SUMMARY_MAX_TOKENS,
        ),
        is_azure=(
            str(getattr(settings, "llm_provider", "") or "").strip().lower()
            == "azure_openai"
            or bool(getattr(settings, "azure_openai_enabled", False))
        ),
        azure_openai_endpoint=getattr(settings, "azure_openai_endpoint", None),
        azure_openai_api_key=getattr(settings, "azure_openai_api_key", None),
        azure_openai_api_version=getattr(
            settings,
            "azure_openai_api_version",
            "2024-10-21",
        ),
        azure_openai_embed_deployment=getattr(
            settings,
            "azure_openai_embed_deployment",
            None,
        ),
        azure_openai_transcription_deployment=getattr(
            settings,
            "azure_openai_transcription_deployment",
            None,
        ),
    )
