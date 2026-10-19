import os
from typing import Optional

EMPTY = {None, "", " ", "\t", "\n"}
_TASK_KINDS = ("chat", "coding", "reasoning", "embedding")
_PROVIDER_KEYS = ("azure", "anthropic", "openai")


def _env(k: str) -> str:
    return os.getenv(k, "") or ""


def _clean_val(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _non_empty_items(d: dict) -> dict:
    return {k: v for k, v in (d or {}).items() if _clean_val(v) is not None}


def _prov_models(prefix: str) -> dict[str, Optional[str]]:
    return {kind: _clean_val(_env(f"{prefix}_MODEL_{kind.upper()}")) for kind in _TASK_KINDS}
