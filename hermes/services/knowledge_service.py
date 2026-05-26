"""Knowledge service — ChromaDB vector store operations."""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from chromadb.config import Settings as ChromaSettings

from hermes.config import get_config
from hermes.logging import get_logger
from hermes.models.domain import (
    Chunk,
    DocumentRecord,
    DocumentType,
    IngestResult,
    SearchResult,
)
from hermes.processing.pipeline import DocumentProcessor

logger = get_logger("knowledge")

_COLLECTION_NAME = "hermes_knowledge"


class _HashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic hash-based embedding for environments without model downloads.

    Produces a fixed-size vector from a text hash.
    Not suitable for real semantic search — use for testing or as a fallback.
    """

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            # Expand hash to desired dimension
            repeated = (h * ((self._dim // len(h)) + 1))[:self._dim]
            vec = [float(b) / 255.0 for b in repeated]
            embeddings.append(vec)
        return embeddings


class KnowledgeService:
    """Manages the vector store — ingestion, search, and document management."""

    def __init__(
        self,
        embedding_fn: EmbeddingFunction | None = None,
    ) -> None:
        cfg = get_config().vectordb
        persist_dir = Path(cfg.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Use provided embedding function, or fall back to hash-based one
        # (avoids model download issues in corporate / offline environments).
        # For production with Ollama: pass OllamaEmbeddingFunction here.
        ef = embedding_fn or _HashEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )
        self._processor = DocumentProcessor()
        logger.info(
            "KnowledgeService ready (collection=%s, docs=%d)",
            _COLLECTION_NAME,
            self._collection.count(),
        )

    # --- Ingestion ---

    def ingest_file(self, file_path: str | Path, document_name: str | None = None) -> IngestResult:
        """Ingest a single file: parse → chunk → store in ChromaDB.

        Args:
            file_path: Path to the file to ingest.
            document_name: Display name to store in the knowledge base.
                           Defaults to the file's own name if not provided.
        """
        path = Path(file_path)
        start = time.perf_counter()
        name = document_name or path.name

        chunks, doc_type = self._processor.process(path)
        if not chunks:
            raise ValueError(f"No text extracted from {path.name}")

        doc_id = uuid.uuid4().hex[:12]

        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        documents = [c.text for c in chunks]
        metadatas = [
            {**c.metadata, "document_id": doc_id, "document_name": name}
            for c in chunks
        ]

        # Send in batches to avoid hitting embedding API request-size limits.
        batch_size = 96
        for start_idx in range(0, len(ids), batch_size):
            end_idx = start_idx + batch_size
            self._collection.add(
                ids=ids[start_idx:end_idx],
                documents=documents[start_idx:end_idx],
                metadatas=metadatas[start_idx:end_idx],
            )

        elapsed = time.perf_counter() - start
        logger.info(
            "Ingested %s → %d chunks in %.2fs (id=%s)",
            name, len(chunks), elapsed, doc_id,
        )

        return IngestResult(
            document_id=doc_id,
            document_name=name,
            doc_type=doc_type,
            chunks_created=len(chunks),
            processing_time_seconds=round(elapsed, 3),
        )

    # --- Search ---

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Semantic search across all ingested documents."""
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
        )

        search_results: list[SearchResult] = []
        if results["documents"] and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
            dists = results["distances"][0] if results["distances"] else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                # ChromaDB returns distance; convert to similarity score (cosine)
                score = max(0.0, 1.0 - dist)
                search_results.append(SearchResult(
                    text=doc,
                    document_name=meta.get("document_name", "unknown"),
                    score=round(score, 4),
                    metadata=meta,
                ))

        return search_results

    # --- Document Management ---

    def list_documents(self) -> list[DocumentRecord]:
        """List all ingested documents (unique by document_id)."""
        all_meta = self._collection.get(include=["metadatas"])
        if not all_meta["metadatas"]:
            return []

        # Group by document_id
        doc_map: dict[str, dict] = {}
        for meta in all_meta["metadatas"]:
            did = meta.get("document_id", "")
            if did not in doc_map:
                doc_map[did] = {
                    "document_id": did,
                    "name": meta.get("document_name", "unknown"),
                    "doc_type": meta.get("doc_type", "unknown"),
                    "count": 0,
                }
            doc_map[did]["count"] += 1

        return [
            DocumentRecord(
                document_id=info["document_id"],
                name=info["name"],
                file_path="",
                doc_type=DocumentType(info["doc_type"]) if info["doc_type"] in [e.value for e in DocumentType] else DocumentType.TEXT,
                chunks_count=info["count"],
            )
            for info in doc_map.values()
        ]

    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a document by its ID."""
        # Find all chunk IDs belonging to this document
        all_data = self._collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        if not all_data["ids"]:
            return False

        self._collection.delete(ids=all_data["ids"])
        logger.info("Deleted document %s (%d chunks)", document_id, len(all_data["ids"]))
        return True

    def get_document(self, document_id: str) -> DocumentRecord | None:
        """Get metadata for a specific document."""
        all_data = self._collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        if not all_data["ids"]:
            return None

        meta = all_data["metadatas"][0]
        doc_type_str = meta.get("doc_type", "text")
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            doc_type = DocumentType.TEXT

        return DocumentRecord(
            document_id=document_id,
            name=meta.get("document_name", "unknown"),
            file_path="",
            doc_type=doc_type,
            chunks_count=len(all_data["ids"]),
        )

    @property
    def total_chunks(self) -> int:
        """Total number of chunks in the collection."""
        return self._collection.count()
