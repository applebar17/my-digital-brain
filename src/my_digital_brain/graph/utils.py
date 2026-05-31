from __future__ import annotations

import json
import re
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def dump_change_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def merge_unique_values(existing: list[Any], additions: list[Any]) -> list[Any]:
    merged = list(existing)
    for value in additions:
        if value not in merged:
            merged.append(value)
    return merged
