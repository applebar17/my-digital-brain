from __future__ import annotations

from fastapi.testclient import TestClient

from my_digital_brain.api.main import create_app
from my_digital_brain.api.routes import health as health_routes


def test_health_endpoint_has_dependency_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        health_routes,
        "graph_health",
        lambda: {"name": "neo4j", "healthy": True},
    )
    monkeypatch.setattr(
        health_routes,
        "relational_health",
        lambda: {"name": "postgres", "healthy": True},
    )
    monkeypatch.setattr(
        health_routes,
        "vector_health",
        lambda: {"name": "chroma", "healthy": True},
    )
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert set(payload["dependencies"]) == {"graph", "relational", "vector"}
