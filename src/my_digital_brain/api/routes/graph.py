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
    ChangeRecordCreateRequest,
    ContradictionCreateRequest,
    ContradictionUpdateRequest,
    EntityDetailResult,
    GraphAnalyticsSummary,
    GraphContextPackage,
    GraphViewResult,
    LifecycleTransitionRequest,
    MapViewResult,
    MergeCreateRequest,
    MergeUpdateRequest,
    NeighborhoodResult,
    NodePatchRequest,
    NodeSearchResult,
    NodeUpsertRequest,
    RelationshipContextDetailResult,
    RelationshipResult,
    RelationshipStateCreateRequest,
    RelationshipUpsertRequest,
    TimelineResult,
)
from my_digital_brain.graph.service import GraphService
from my_digital_brain.ingestion.contracts import (
    MultiScopeRetrievalResult,
    VectorScopeSearchRequest,
)
from my_digital_brain.rag.models import SemanticMemorySearchResult
from my_digital_brain.rag.search import SemanticMemorySearchService
from my_digital_brain.rag.scoped_search import VectorScopeSearchService

router = APIRouter(prefix="/graph", tags=["graph"])


def get_graph_service() -> Generator[GraphService]:
    from my_digital_brain.config import get_settings
    from my_digital_brain.graph.repository import GraphRepository
    from my_digital_brain.storage.graph import GraphClient

    settings = get_settings()
    with GraphClient.from_settings(settings) as client:
        yield GraphService(GraphRepository(client))


def get_vector_scope_search_service() -> Generator[VectorScopeSearchService]:
    from my_digital_brain.ai.client.settings import genai_settings_from_app_settings
    from my_digital_brain.ai.router import StaticModelRouter
    from my_digital_brain.chat.factory import build_ai_provider
    from my_digital_brain.config import get_settings
    from my_digital_brain.storage.relational import RelationalSessionProvider
    from my_digital_brain.storage.vector import ChromaVectorStore
    from my_digital_brain.rag.vector_records import VectorRecordStore

    settings = get_settings()
    provider = build_ai_provider(settings)
    router = StaticModelRouter(
        settings=genai_settings_from_app_settings(settings),
        provider=settings.normalized_llm_provider,
    )
    relational = RelationalSessionProvider.from_settings(settings)
    try:
        yield VectorScopeSearchService(
            embedding_provider=provider,
            vector_store=ChromaVectorStore.from_settings(settings),
            vector_record_store=VectorRecordStore(relational),
            model_router=router,
        )
    finally:
        relational.dispose()


def get_semantic_search_service() -> Generator[SemanticMemorySearchService]:
    from my_digital_brain.ai.client.settings import genai_settings_from_app_settings
    from my_digital_brain.ai.router import StaticModelRouter
    from my_digital_brain.chat.factory import build_ai_provider
    from my_digital_brain.config import get_settings
    from my_digital_brain.graph.repository import GraphRepository
    from my_digital_brain.storage.graph import GraphClient
    from my_digital_brain.storage.relational import RelationalSessionProvider
    from my_digital_brain.storage.vector import ChromaVectorStore
    from my_digital_brain.rag.vector_records import VectorRecordStore

    settings = get_settings()
    provider = build_ai_provider(settings)
    model_router = StaticModelRouter(
        settings=genai_settings_from_app_settings(settings),
        provider=settings.normalized_llm_provider,
    )
    relational = RelationalSessionProvider.from_settings(settings)
    try:
        with GraphClient.from_settings(settings) as client:
            yield SemanticMemorySearchService(
                graph_service=GraphService(GraphRepository(client)),
                embedding_provider=provider,
                vector_store=ChromaVectorStore.from_settings(settings),
                vector_record_store=VectorRecordStore(relational),
                model_router=model_router,
            )
    finally:
        relational.dispose()


def graph_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
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


@router.post("/search/vector-scopes", response_model=MultiScopeRetrievalResult)
def vector_scope_search(
    request: VectorScopeSearchRequest,
    service: VectorScopeSearchService = Depends(get_vector_scope_search_service),
) -> MultiScopeRetrievalResult:
    try:
        return service.search(request)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/search/semantic", response_model=SemanticMemorySearchResult)
def semantic_search(
    query: str,
    limit: int = Query(default=10, ge=1, le=100),
    include_archived: bool = False,
    include_history: bool = False,
    graph_focus: str = Query(default="broad", pattern="^(narrow|adaptive|broad)$"),
    target_ids: list[str] | None = Query(default=None),
    service: SemanticMemorySearchService = Depends(get_semantic_search_service),
) -> SemanticMemorySearchResult:
    try:
        return service.search_semantic(
            query,
            limit=limit,
            include_archived=include_archived,
            include_history=include_history,
            graph_focus=graph_focus,  # type: ignore[arg-type]
            target_ids=target_ids or [],
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/search/hybrid", response_model=SemanticMemorySearchResult)
def hybrid_search(
    query: str,
    label: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    include_archived: bool = False,
    include_history: bool = False,
    graph_focus: str = Query(default="broad", pattern="^(narrow|adaptive|broad)$"),
    target_ids: list[str] | None = Query(default=None),
    service: SemanticMemorySearchService = Depends(get_semantic_search_service),
) -> SemanticMemorySearchResult:
    try:
        return service.search_hybrid(
            query,
            label=label,
            limit=limit,
            include_archived=include_archived,
            include_history=include_history,
            graph_focus=graph_focus,  # type: ignore[arg-type]
            target_ids=target_ids or [],
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


@router.post("/relationship-contexts/{context_id}/states", response_model=NodeSearchResult)
def create_relationship_state(
    context_id: str,
    request: RelationshipStateCreateRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.create_relationship_state(
            context_id,
            request.properties,
            make_current=request.make_current,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/relationship-contexts/{context_id}/states", response_model=list[NodeSearchResult])
def get_relationship_states(
    context_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[NodeSearchResult]:
    try:
        return service.get_relationship_states(context_id, limit=limit)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get(
    "/relationship-contexts/{context_id}/detail",
    response_model=RelationshipContextDetailResult,
)
def get_relationship_context_detail(
    context_id: str,
    include_state_history: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> RelationshipContextDetailResult:
    try:
        return service.get_relationship_context_detail(
            context_id,
            include_state_history=include_state_history,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/change-records", response_model=NodeSearchResult)
def create_change_record(
    request: ChangeRecordCreateRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.create_change_record(request.properties)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/targets/{target_id}/changes", response_model=list[NodeSearchResult])
def get_change_records_for_target(
    target_id: str,
    target_kind: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[NodeSearchResult]:
    try:
        return service.get_change_records_for_target(
            target_id,
            target_kind=target_kind,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/nodes/{node_id}/lifecycle", response_model=NodeSearchResult)
def transition_node_lifecycle(
    node_id: str,
    request: LifecycleTransitionRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.transition_node_lifecycle(node_id, request)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/relationships/{relationship_id}/lifecycle", response_model=RelationshipResult)
def transition_relationship_lifecycle(
    relationship_id: str,
    request: LifecycleTransitionRequest,
    service: GraphService = Depends(get_graph_service),
) -> RelationshipResult:
    try:
        return service.transition_relationship_lifecycle(relationship_id, request)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/contradictions", response_model=NodeSearchResult)
def create_contradiction(
    request: ContradictionCreateRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.create_contradiction(request.properties, target_ids=request.target_ids)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/contradictions", response_model=list[NodeSearchResult])
def query_contradictions(
    target_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    contradiction_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[NodeSearchResult]:
    try:
        return service.query_contradictions(
            target_id=target_id,
            status=status,
            severity=severity,
            contradiction_type=contradiction_type,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.patch("/contradictions/{contradiction_id}", response_model=NodeSearchResult)
def update_contradiction(
    contradiction_id: str,
    request: ContradictionUpdateRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.update_contradiction(contradiction_id, request.properties)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/merges", response_model=NodeSearchResult)
def create_merge(
    request: MergeCreateRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.create_merge_record(
            canonical_node_id=request.canonical_node_id,
            merged_node_ids=request.merged_node_ids,
            reason=request.reason,
            performed_by=request.performed_by,
            source_ids=request.source_ids,
            extraction_run_ids=request.extraction_run_ids,
            metadata=request.metadata,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/merges", response_model=list[NodeSearchResult])
def query_merges(
    canonical_node_id: str | None = None,
    merged_node_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[NodeSearchResult]:
    try:
        return service.query_merges(
            canonical_node_id=canonical_node_id,
            merged_node_id=merged_node_id,
            status=status,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.patch("/merges/{merge_id}", response_model=NodeSearchResult)
def update_merge(
    merge_id: str,
    request: MergeUpdateRequest,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.update_merge_record(merge_id, request.properties)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.post("/merges/{merge_id}/apply", response_model=NodeSearchResult)
def apply_merge(
    merge_id: str,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.apply_merge(merge_id)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/canonical", response_model=NodeSearchResult)
def get_canonical_node(
    node_id: str,
    service: GraphService = Depends(get_graph_service),
) -> NodeSearchResult:
    try:
        return service.get_canonical_node(node_id)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/detail", response_model=EntityDetailResult)
def get_entity_detail(
    node_id: str,
    include_history: bool = False,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> EntityDetailResult:
    try:
        return service.get_entity_detail(
            node_id,
            include_history=include_history,
            include_archived=include_archived,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/memories", response_model=GraphViewResult)
def get_memories_for_node(
    node_id: str,
    include_history: bool = False,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> GraphViewResult:
    try:
        return service.get_memories_for_node(
            node_id,
            include_history=include_history,
            include_archived=include_archived,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/targets/{target_id}/evidence", response_model=list[NodeSearchResult])
def get_source_evidence(
    target_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> list[NodeSearchResult]:
    try:
        return service.get_source_evidence(target_id, limit=limit)
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/timeline", response_model=TimelineResult)
def get_timeline_for_node(
    node_id: str,
    from_time: str | None = None,
    to_time: str | None = None,
    include_history: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> TimelineResult:
    try:
        return service.get_timeline_for_node(
            node_id,
            from_time=from_time,
            to_time=to_time,
            include_history=include_history,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/views/neighborhood", response_model=GraphViewResult)
def get_neighborhood_view(
    seed_id: str,
    depth: int = Query(default=1, ge=1, le=3),
    include_history: bool = False,
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> GraphViewResult:
    try:
        return service.get_neighborhood_view(
            seed_id=seed_id,
            depth=depth,
            include_history=include_history,
            include_archived=include_archived,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/views/map", response_model=MapViewResult)
def get_map_view(
    seed_id: str | None = None,
    city: str | None = None,
    country: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> MapViewResult:
    try:
        return service.get_map_view(
            seed_id=seed_id,
            city=city,
            country=country,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/nodes/{node_id}/context-package", response_model=GraphContextPackage)
def get_context_package(
    node_id: str,
    include_history: bool = True,
    timeline_limit: int = Query(default=20, ge=1, le=200),
    relationship_limit: int = Query(default=50, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> GraphContextPackage:
    try:
        return service.get_context_package(
            node_id,
            include_history=include_history,
            timeline_limit=timeline_limit,
            relationship_limit=relationship_limit,
        )
    except Exception as exc:
        raise graph_http_error(exc) from exc


@router.get("/analytics/summary", response_model=GraphAnalyticsSummary)
def get_analytics_summary(
    include_archived: bool = False,
    limit: int = Query(default=20, ge=1, le=200),
    service: GraphService = Depends(get_graph_service),
) -> GraphAnalyticsSummary:
    try:
        return service.get_analytics_summary(include_archived=include_archived, limit=limit)
    except Exception as exc:
        raise graph_http_error(exc) from exc
