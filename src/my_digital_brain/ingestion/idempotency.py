from __future__ import annotations

from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5


def idempotency_key(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts if part not in (None, ""))
    return sha256(payload.encode("utf-8")).hexdigest()


def deterministic_uuid(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"my-digital-brain:ingestion:{key}"))
