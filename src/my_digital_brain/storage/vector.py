from __future__ import annotations

from typing import Any, Protocol

import chromadb

from my_digital_brain.config import Settings


class VectorStore(Protocol):
    def upsert_embedding(
        self,
        collection: str,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
        document: str | None = None,
    ) -> None:
        ...

    def search(
        self,
        collection: str,
        embedding: list[float],
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def delete(self, collection: str, vector_id: str) -> None:
        ...

    def health_check(self) -> None:
        ...


class ChromaVectorStore:
    def __init__(self, client: chromadb.HttpClient, collection_prefix: str) -> None:
        self.client = client
        self.collection_prefix = collection_prefix

    @classmethod
    def from_settings(cls, settings: Settings) -> "ChromaVectorStore":
        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        return cls(client=client, collection_prefix=settings.chroma_collection_prefix)

    def collection_name(self, collection: str) -> str:
        return f"{self.collection_prefix}_{collection}"

    def upsert_embedding(
        self,
        collection: str,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
        document: str | None = None,
    ) -> None:
        chroma_collection = self.client.get_or_create_collection(self.collection_name(collection))
        chroma_collection.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            metadatas=[metadata or {}],
            documents=[document or ""],
        )

    def search(
        self,
        collection: str,
        embedding: list[float],
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        chroma_collection = self.client.get_or_create_collection(self.collection_name(collection))
        results = chroma_collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where=where,
        )
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        return [
            {"id": item_id, "distance": distance, "metadata": metadata, "document": document}
            for item_id, distance, metadata, document in zip(ids, distances, metadatas, documents, strict=False)
        ]

    def delete(self, collection: str, vector_id: str) -> None:
        chroma_collection = self.client.get_or_create_collection(self.collection_name(collection))
        chroma_collection.delete(ids=[vector_id])

    def health_check(self) -> None:
        self.client.heartbeat()
