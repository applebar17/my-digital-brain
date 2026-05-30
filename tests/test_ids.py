from __future__ import annotations

from uuid import UUID

import pytest

from my_digital_brain.core.ids import IdAliasMapper, new_uuid


def test_new_uuid_returns_valid_uuid() -> None:
    value = new_uuid()

    assert str(UUID(value)) == value


def test_alias_mapper_creates_stable_scoped_aliases() -> None:
    first_id = new_uuid()
    second_id = new_uuid()
    mapper = IdAliasMapper()

    assert mapper.alias_for(first_id, "NODE") == "NODE_000001"
    assert mapper.alias_for(second_id, "NODE") == "NODE_000002"
    assert mapper.alias_for(first_id, "NODE") == "NODE_000001"


def test_alias_mapper_resolves_aliases() -> None:
    internal_id = new_uuid()
    mapper = IdAliasMapper()
    alias = mapper.alias_for(internal_id, "CLAIM")

    assert mapper.resolve(alias) == internal_id


def test_alias_mapper_rejects_unknown_aliases() -> None:
    mapper = IdAliasMapper()

    with pytest.raises(ValueError, match="Unknown LLM-facing id alias"):
        mapper.resolve("NODE_999999")
