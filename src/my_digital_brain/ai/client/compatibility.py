from __future__ import annotations

from typing import Any


def is_gpt5_model(model: str | None) -> bool:
    normalized = str(model or "").lower().replace("_", "-")
    compact = normalized.replace("-", "")
    return "gpt5" in compact or "gpt-5" in normalized


def supports_explicit_temperature(model: str | None) -> bool:
    return not is_gpt5_model(model)


def completion_token_parameter(model: str | None) -> str:
    return "max_completion_tokens" if is_gpt5_model(model) else "max_tokens"


def apply_chat_completion_compatibility(params: dict[str, Any]) -> dict[str, Any]:
    model = str(params.get("model") or "")
    updated = dict(params)
    if not supports_explicit_temperature(model):
        updated.pop("temperature", None)
    if completion_token_parameter(model) == "max_completion_tokens":
        max_tokens = updated.pop("max_tokens", None)
        if max_tokens is not None and "max_completion_tokens" not in updated:
            updated["max_completion_tokens"] = max_tokens
    return updated
