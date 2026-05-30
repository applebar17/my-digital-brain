from __future__ import annotations

from fastapi import APIRouter

from my_digital_brain.config import get_settings
from my_digital_brain.storage.graph import GraphClient
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.vector import ChromaVectorStore

router = APIRouter(tags=["health"])


def status_payload(name: str, healthy: bool, detail: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "healthy": healthy}
    if detail:
        payload["detail"] = detail
    return payload


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "dependencies": {
            "graph": graph_health(),
            "relational": relational_health(),
            "vector": vector_health(),
        },
    }


@router.get("/health/graph")
def graph_health() -> dict[str, object]:
    settings = get_settings()
    try:
        with GraphClient.from_settings(settings) as client:
            client.health_check()
        return status_payload("neo4j", True)
    except Exception as exc:  # pragma: no cover - exercised in integration tests
        return status_payload("neo4j", False, str(exc))


@router.get("/health/relational")
def relational_health() -> dict[str, object]:
    settings = get_settings()
    try:
        provider = RelationalSessionProvider.from_settings(settings)
        provider.health_check()
        provider.dispose()
        return status_payload(settings.relational_backend, True)
    except Exception as exc:  # pragma: no cover - exercised in integration tests
        return status_payload(settings.relational_backend, False, str(exc))


@router.get("/health/vector")
def vector_health() -> dict[str, object]:
    settings = get_settings()
    try:
        store = ChromaVectorStore.from_settings(settings)
        store.health_check()
        return status_payload("chroma", True)
    except Exception as exc:  # pragma: no cover - exercised in integration tests
        return status_payload("chroma", False, str(exc))
