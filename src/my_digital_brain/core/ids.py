from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID, uuid4


def new_uuid() -> str:
    return str(uuid4())


def validate_uuid(value: str) -> str:
    return str(UUID(value))


@dataclass
class IdAliasMapper:
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    alias_to_id: dict[str, str] = field(default_factory=dict)
    id_to_alias: dict[str, str] = field(default_factory=dict)

    def alias_for(self, internal_id: str, prefix: str) -> str:
        normalized_id = validate_uuid(internal_id)
        normalized_prefix = prefix.upper()
        existing = self.id_to_alias.get(normalized_id)
        if existing:
            return existing

        self.counters[normalized_prefix] += 1
        alias = f"{normalized_prefix}_{self.counters[normalized_prefix]:06d}"
        self.alias_to_id[alias] = normalized_id
        self.id_to_alias[normalized_id] = alias
        return alias

    def resolve(self, alias: str) -> str:
        try:
            return self.alias_to_id[alias]
        except KeyError as exc:
            raise ValueError(f"Unknown LLM-facing id alias: {alias}") from exc

    def export_context_map(self) -> dict[str, str]:
        return dict(self.alias_to_id)
