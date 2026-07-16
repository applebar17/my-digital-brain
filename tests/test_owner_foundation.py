from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from my_digital_brain.api import main as api_main
from my_digital_brain.config import Settings
from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.graph.exceptions import GraphConflictError, GraphValidationError
from my_digital_brain.graph.models import PersonNode
from my_digital_brain.graph.owner import OwnerNodeManager
from my_digital_brain.graph.service import GraphService
from my_digital_brain.ingestion.contracts import SourceRecordRef
from my_digital_brain.ingestion.enums import SourceChannel, SourceType
from my_digital_brain.ingestion.graph_context_pack import WholeSourceGraphContextPackBuilder


class FakeOwnerRepository:
    def __init__(self, nodes: list[dict[str, object]] | None = None) -> None:
        self.nodes = {
            str(node["properties"]["id"]): node
            for node in (nodes or [])
        }

    def get_node(self, node_id: str) -> dict[str, object] | None:
        return self.nodes.get(node_id)

    def find_owner_nodes(self) -> list[dict[str, object]]:
        return [
            node
            for node in self.nodes.values()
            if node["label"] == "Person" and node["properties"].get("is_owner") is True
        ]

    def upsert_node(self, label: str, properties: dict[str, object]) -> dict[str, object]:
        node = {"label": label, "labels": [label], "properties": dict(properties)}
        self.nodes[str(properties["id"])] = node
        return node


class FakeGraphWriteRepository(FakeOwnerRepository):
    def patch_node(self, node_id: str, properties: dict[str, object]) -> dict[str, object] | None:
        node = self.nodes.get(node_id)
        if node is None:
            return None
        node["properties"].update(properties)
        return node

    def search_nodes(self, **_kwargs: object) -> list[dict[str, object]]:
        return list(self.nodes.values())


def _node(label: str, node_id: str, **properties: object) -> dict[str, object]:
    return {
        "label": label,
        "labels": [label],
        "properties": {"id": node_id, **properties},
    }


def test_person_defaults_to_non_owner() -> None:
    person = PersonNode(display_name="Alessandro")

    assert person.is_owner is False
    assert person.model_dump(mode="json")["is_owner"] is False


def test_normal_person_writes_default_to_false_and_reject_true() -> None:
    service = GraphService(FakeGraphWriteRepository())

    person = service.upsert_node("Person", {"id": "person-1", "display_name": "Someone"})
    assert person.properties["is_owner"] is False

    with pytest.raises(GraphValidationError, match="cannot create or promote"):
        service.upsert_node(
            "Person",
            {"id": "person-2", "display_name": "Owner", "is_owner": True},
        )
    with pytest.raises(GraphValidationError, match="cannot create or promote"):
        service.upsert_node(
            "Person",
            {"id": "person-3", "display_name": "Owner", "is_owner": "true"},
        )


def test_normal_person_patches_cannot_change_owner_flag() -> None:
    service = GraphService(FakeGraphWriteRepository())
    person = service.upsert_node("Person", {"id": "person-1"})

    with pytest.raises(GraphValidationError, match="is_owner"):
        service.patch_node(person.properties["id"], {"is_owner": True})
    with pytest.raises(GraphValidationError, match="is_owner"):
        service.patch_node(person.properties["id"], {"is_owner": False})


def test_non_person_nodes_reject_owner_flag() -> None:
    service = GraphService(FakeGraphWriteRepository())

    with pytest.raises(GraphValidationError):
        service.upsert_node("Topic", {"id": "topic-1", "is_owner": False})


def test_owner_bootstrap_is_idempotent_and_resolves_alias() -> None:
    repository = FakeOwnerRepository()
    manager = OwnerNodeManager(repository, Settings(owner_graph_node_id="person:owner"))

    owner = manager.ensure_owner()
    repeated = manager.ensure_owner()

    assert owner["properties"]["id"] == "person:owner"
    assert owner["properties"]["is_owner"] is True
    assert repeated["properties"]["id"] == "person:owner"
    assert len(repository.nodes) == 1
    assert manager.resolve_owner_alias(OWNER_ALIAS) == "person:owner"


def test_owner_bootstrap_rejects_wrong_existing_node() -> None:
    repository = FakeOwnerRepository([_node("Person", "person:owner", is_owner=False)])
    manager = OwnerNodeManager(repository, Settings(owner_graph_node_id="person:owner"))

    with pytest.raises(GraphConflictError, match="explicit repair"):
        manager.ensure_owner()


def test_owner_bootstrap_rejects_wrong_label() -> None:
    repository = FakeOwnerRepository([_node("Topic", "person:owner")])
    manager = OwnerNodeManager(repository, Settings(owner_graph_node_id="person:owner"))

    with pytest.raises(GraphConflictError, match="already used"):
        manager.ensure_owner()


def test_owner_bootstrap_rejects_multiple_owners() -> None:
    repository = FakeOwnerRepository(
        [
            _node("Person", "person:owner", is_owner=True),
            _node("Person", "person:other", is_owner=True),
        ]
    )
    manager = OwnerNodeManager(repository, Settings(owner_graph_node_id="person:owner"))

    with pytest.raises(GraphConflictError, match="multiple owner"):
        manager.ensure_owner()


def test_context_owner_alias_prefers_configured_canonical_id() -> None:
    source = SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="hello",
        metadata={"owner_graph_node_id": "legacy-owner-id"},
    )
    builder = WholeSourceGraphContextPackBuilder(owner_graph_node_id="person:owner")

    pack = builder.build(source)

    assert pack.alias_map[OWNER_ALIAS] == "person:owner"


def test_initialize_owner_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        owner_graph_node_id="person:owner",
        owner_bootstrap_max_attempts=3,
        owner_bootstrap_retry_delay_seconds=0,
    )
    attempts = 0

    class FakeClient:
        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class FakeOwnerManager:
        def __init__(self, _repository: object, _settings: Settings) -> None:
            pass

        def ensure_owner(self) -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionError("Neo4j is starting")

    monkeypatch.setattr(api_main, "get_settings", lambda: settings)
    monkeypatch.setattr(api_main.GraphClient, "from_settings", lambda _settings: FakeClient())
    monkeypatch.setattr(api_main, "OwnerNodeManager", FakeOwnerManager)

    api_main.initialize_owner()

    assert attempts == 3


def test_application_lifespan_initializes_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(api_main, "initialize_owner", lambda: calls.append("initialized"))

    with TestClient(api_main.create_app()):
        pass

    assert calls == ["initialized"]
