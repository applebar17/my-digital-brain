from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query

from my_digital_brain.graph.exceptions import (
    GraphConflictError,
    GraphNotFoundError,
    GraphValidationError,
)
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    NeighborhoodResult,
    NodePatchRequest,
    NodeSearchResult,
    NodeUpsertRequest,
    RelationshipResult,
    RelationshipUpsertRequest,
)
from my_digital_brain.graph.service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])


def get_graph_service() -> Generator[GraphService]:
    from my_digital_brain.config import get_settings
    from my_digital_brain.graph.repository import GraphRepository
    from my_digital_brain.storage.graph import GraphClient

    settings = get_settings()
    with GraphClient.from_settings(settings) as client:
        yield GraphService(GraphRepository(client))


def graph_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GraphValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, GraphNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, GraphConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.post("/nodes", response_model=NodeSearchResult)
def upsert_node(
    request: NodeUpsertRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.upsert_node(request.label, request.properties)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/search", response_model=list[NodeSearchResult])
def search_nodes(
    label: str | None = None,
    query: str | None = None,
    lifecycle_state: str | None = None,
    privacy_level: str | None = None,
    trust_level: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[NodeSearchResult]:
    try:
        return service.search_nodes(
            label=label,
            query=query,
            lifecycle_state=lifecycle_state,
            privacy_level=privacy_level,
            trust_level=trust_level,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}", response_model=NodeSearchResult)
def get_node(
    node_id: str,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.get_node(node_id)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.patch("/nodes/{node_id}", response_model=NodeSearchResult)
def patch_node(
    node_id: str,
    request: NodePatchRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.patch_node(node_id, request.properties)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/relationships", response_model=RelationshipResult)
def upsert_relationship(
    request: RelationshipUpsertRequest,
    service: GraphService = Depends(get_graph_service),
) -> RelationshipResult:
    try:
        return service.upsert_relationship(
            request.type,
            request.from_id,
            request.to_id,
            request.properties,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/relationships", response_model=list[RelationshipResult])
def get_node_relationships(
    node_id: str,
    relationship_type: str | None = None,
    direction: str = "both",
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[RelationshipResult]:
    try:
        return service.get_node_relationships(
            node_id,
            relationship_type=relationship_type,
            direction=direction,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/neighborhood", response_model=NeighborhoodResult)
def get_neighborhood(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=3),
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> NeighborhoodResult:
    try:
        return service.get_neighborhood(node_id, depth=depth, limit=limit)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/affective-context", response_model=AffectiveContextResult)
def get_affective_context(
    node_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> AffectiveContextResult:
    try:
        return service.get_affective_context(node_id, limit=limit)
    except Exception as exc:
        raise graph_http_error(exc) from exc
