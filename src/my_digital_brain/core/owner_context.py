from __future__ import annotations

from typing import Any, Literal
import json

from pydantic import BaseModel, ConfigDict, Field


class OwnerSnapshot(BaseModel):
    """Minimal model-facing identity projection for the graph owner."""

    model_config = ConfigDict(extra="forbid")

    ref: Literal["OWNER"] = "OWNER"
    label: Literal["Person"] = "Person"
    role: Literal["owner"] = "owner"
    display_name: str | None = None
    name_variants: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    @classmethod
    def from_properties(cls, properties: dict[str, Any] | None) -> "OwnerSnapshot":
        properties = properties or {}
        display_name = _text(properties.get("display_name"))
        variants = _unique_text(
            [display_name, _text(properties.get("normalized_name"))]
        )
        aliases = _unique_text(properties.get("aliases"))
        return cls(
            display_name=display_name,
            name_variants=variants,
            aliases=aliases,
        )


OWNER_PROMPT_CONTRACT = """# Owner interaction contract
- `OWNER` is the existing canonical Person node representing the current user.
- Map first-person references in the user's own words (`I`, `me`, `my`) to `OWNER`.
- Do not map first-person text inside quotations or third-party content without evidence.
- Use `OWNER` as the only owner reference. Never invent or emit a persisted graph ID.
- Never create a second owner, create a Person for the owner, or set `Person.is_owner`.
- Stable self-information belongs on ProfileMemory through DESCRIBES_USER -> OWNER.
- Do not place stable traits, preferences, goals, or personality fields directly on Person.
- Keep temporary moods and isolated events in episodic memory/perception structures.
- Preserve provenance and original wording. Inferred traits are unconfirmed and require confirmation.
"""


def owner_prompt_block(snapshot: OwnerSnapshot | dict[str, Any] | None) -> str:
    payload = snapshot.model_dump(mode="json", exclude_none=True) if hasattr(snapshot, "model_dump") else snapshot
    identity = json.dumps(payload or OwnerSnapshot().model_dump(mode="json"), ensure_ascii=False)
    return f"{OWNER_PROMPT_CONTRACT}\nOwner snapshot:\n```json\n{identity}\n```"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _unique_text(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _text(item)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            result.append(text)
    return result
