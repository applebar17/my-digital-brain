from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.protocols import EmbeddingProvider, ModelRouter
from my_digital_brain.ai.router import EMBEDDING_TASK, StaticModelRouter
from my_digital_brain.ai.schemas import AIRequestContext, EmbeddingRequest
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.ingestion.contracts import (
    GraphNodeWrite,
    IngestionResult,
    MultiScopeVectorConfig,
    V1_VECTOR_DIMENSIONS,
    default_v1_vector_scope_config,
)
from my_digital_brain.rag.models import (
    GraphVectorizationResult,
    VECTOR_STORE_CHROMA,
    VECTOR_SCOPES_COLLECTION,
    EmbeddingDocument,
    VectorRecordData,
)
from my_digital_brain.rag.text_builder import EmbeddingTextBuilder
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.vector import VectorStore

logger = logging.getLogger(__name__)


class GraphVectorizationService:
    """Vectorize successful graph writes through deterministic embedding documents."""

    def __init__(
        self,
        *,
        graph_service: Any,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        vector_record_store: VectorRecordStore,
        model_router: ModelRouter | None = None,
        text_builder: EmbeddingTextBuilder | None = None,
        collection: str = VECTOR_SCOPES_COLLECTION,
        vector_config: MultiScopeVectorConfig | None = None,
        vector_store_name: str = VECTOR_STORE_CHROMA,
    ) -> None:
        self.graph_service = graph_service
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.vector_record_store = vector_record_store
        self.model_router = model_router or StaticModelRouter()
        self.text_builder = text_builder or EmbeddingTextBuilder()
        self.collection = collection
        self.vector_config = vector_config or default_v1_vector_scope_config()
        self.scoped_collections = {
            scope.collection for scope in self.vector_config.scopes if scope.enabled
        }
        self.vector_store_name = vector_store_name

    @traceable(name="Graph RAG Vectorize Ingestion Result", run_type="chain")
    def vectorize_ingestion_result(self, result: IngestionResult) -> GraphVectorizationResult:
        if result.write_plan is None:
            return GraphVectorizationResult(status="skipped", collection=self.collection)

        target_ids = self._target_ids_from_ingestion_result(result)
        documents: list[EmbeddingDocument] = []
        skipped_targets: list[str] = []
        archived_records = 0
        unchanged_records = 0

        route = self.model_router.route(
            EMBEDDING_TASK,
            AIRequestContext(
                purpose="graph_vectorization",
                source_id=result.source_id,
                metadata={"ingestion_id": result.ingestion_id},
            ),
        )

        for target_id in target_ids:
            node = self._get_node(target_id)
            if node is None:
                skipped_targets.append(target_id)
                continue
            related_nodes = self._related_nodes(target_id)
            document = self.text_builder.build_for_node(
                node,
                related_nodes=related_nodes,
                embedding_model=route.model,
            )
            if document is None:
                archived_records += self._archive_existing_records(target_id)
                skipped_targets.append(target_id)
                continue
            if document.lifecycle_state in {"archived", "deleted"}:
                archived_records += self._archive_document(document)
                skipped_targets.append(target_id)
                continue
            existing = self.vector_record_store.get_by_vector_id(
                document.vector_id,
                vector_store=self.vector_store_name,
                collection=document.collection,
            )
            if (
                existing is not None
                and existing.builder_version == document.builder_version
                and existing.document_checksum == document.document_checksum
                and existing.lifecycle_state == document.lifecycle_state
            ):
                unchanged_records += 1
                continue
            documents.append(document)

        if not documents:
            return GraphVectorizationResult(
                status="skipped" if skipped_targets else "unchanged",
                collection=self.collection,
                target_count=len(target_ids),
                skipped_targets=skipped_targets,
                unchanged_records=unchanged_records,
                archived_records=archived_records,
            )

        embeddings = self.embedding_provider.embed(
            EmbeddingRequest(
                texts=[document.document for document in documents],
                model=route.model,
                dimensions=V1_VECTOR_DIMENSIONS,
                context=AIRequestContext(
                    purpose="graph_vectorization",
                    source_id=result.source_id,
                    metadata={
                        "ingestion_id": result.ingestion_id,
                        "collection": self.collection,
                    },
                ),
                metadata={"route": route.model_dump(mode="json", exclude_none=True)},
            )
        )
        if len(embeddings.embeddings) != len(documents):
            raise RuntimeError(
                "Embedding provider returned "
                f"{len(embeddings.embeddings)} embeddings for {len(documents)} documents."
            )

        upserted = 0
        records = 0
        for document, embedding in zip(documents, embeddings.embeddings, strict=False):
            self.vector_store.upsert_embedding(
                document.collection,
                document.vector_id,
                embedding,
                metadata=_chroma_metadata(document),
                document=document.document,
            )
            self.vector_record_store.upsert(
                VectorRecordData.from_embedding_document(
                    document,
                    vector_store=self.vector_store_name,
                )
            )
            upserted += 1
            records += 1

        log_event(
            logger,
            "rag.vectorization.done",
            component="rag",
            source_id=result.source_id,
            ingestion_id=result.ingestion_id,
            target_count=len(target_ids),
            documents_built=len(documents),
            embeddings_upserted=upserted,
            vector_records_upserted=records,
            unchanged_records=unchanged_records,
            archived_records=archived_records,
        )
        return GraphVectorizationResult(
            status="ok",
            collection=self.collection,
            target_count=len(target_ids),
            documents_built=len(documents),
            embeddings_upserted=upserted,
            vector_records_upserted=records,
            unchanged_records=unchanged_records,
            archived_records=archived_records,
            skipped_targets=skipped_targets,
        )

    def _target_ids_from_ingestion_result(self, result: IngestionResult) -> list[str]:
        write_plan = result.write_plan
        if write_plan is None:
            return []
        ref_map = dict(result.metadata.get("ref_map") or {})
        targets: list[str] = []
        for write in _node_writes(write_plan):
            target_id = _resolve_write_target(write, ref_map)
            if target_id:
                targets.append(target_id)
        for patch in write_plan.metadata_patches:
            target_id = _resolve_ref(patch.target_ref, ref_map)
            if target_id:
                targets.append(target_id)
        return _dedupe(targets)

    def _get_node(self, node_id: str) -> NodeSearchResult | None:
        try:
            return self.graph_service.get_node(node_id)
        except Exception as exc:
            log_event(
                logger,
                "rag.vectorization.node_missing",
                level="warning",
                component="rag",
                target_id=node_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None

    def _related_nodes(self, node_id: str, *, limit: int = 20) -> list[NodeSearchResult]:
        if not hasattr(self.graph_service, "get_node_relationships"):
            return []
        try:
            relationships = self.graph_service.get_node_relationships(node_id, limit=limit)
        except Exception:
            return []
        related_nodes: list[NodeSearchResult] = []
        for relationship in relationships:
            related_id = relationship.to_id if relationship.from_id == node_id else relationship.from_id
            if related_id == node_id:
                continue
            node = self._get_node(related_id)
            if node is not None:
                related_nodes.append(node)
        return related_nodes

    def _archive_document(self, document: EmbeddingDocument) -> int:
        try:
            self.vector_store.delete(document.collection, document.vector_id)
        except Exception:
            pass
        existing = self.vector_record_store.mark_lifecycle_state(
            document.vector_id,
            "archived",
            vector_store=self.vector_store_name,
            collection=document.collection,
        )
        return 1 if existing is not None else 0

    def _archive_existing_records(self, target_id: str) -> int:
        records = self.vector_record_store.list_by_primary_target(
            target_id,
            collection=None,
            include_archived=False,
        )
        archived = 0
        for record in records:
            if record.collection not in self.scoped_collections:
                continue
            try:
                self.vector_store.delete(record.collection, record.vector_id)
            except Exception:
                pass
            updated = self.vector_record_store.mark_lifecycle_state(
                record.vector_id,
                "archived",
                vector_store=record.vector_store,
                collection=record.collection,
            )
            if updated is not None:
                archived += 1
        return archived


def _node_writes(write_plan: Any) -> list[GraphNodeWrite]:
    return [
        *write_plan.nodes_to_create,
        *write_plan.nodes_to_update,
        *write_plan.claims_to_create,
        *write_plan.perceptions_to_create,
        *write_plan.relationship_contexts_to_create,
        *write_plan.memory_logs_to_create,
    ]


def _resolve_write_target(write: GraphNodeWrite, ref_map: dict[str, str]) -> str | None:
    if write.local_ref in ref_map:
        return ref_map[write.local_ref]
    if write.target_ref:
        return _resolve_ref(write.target_ref, ref_map)
    node_id = write.properties.get("id")
    return str(node_id) if node_id else None


def _resolve_ref(value: str, ref_map: dict[str, str]) -> str | None:
    return ref_map.get(value, value)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _chroma_metadata(document: EmbeddingDocument) -> dict[str, str | int | float | bool]:
    return {
        "primary_target_id": document.primary_target_id,
        "primary_target_label": document.primary_target_label,
        "canonical_target_id": document.canonical_target_id or "",
        "related_target_ids": ",".join(document.related_target_ids),
        "source_ids": ",".join(document.source_ids),
        "relationship_ids": ",".join(document.relationship_ids),
        "hit_role": document.hit_role,
        "embedding_scope": document.embedding_scope,
        "builder_version": document.builder_version,
        "document_checksum": document.document_checksum,
        "lifecycle_state": document.lifecycle_state,
    }
