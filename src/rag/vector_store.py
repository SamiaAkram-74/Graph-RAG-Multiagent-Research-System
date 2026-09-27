"""
Vector store — manages document storage and similarity search using
ChromaDB or FAISS.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from loguru import logger

from src.config import get_settings


class VectorStore:
    """Abstraction over ChromaDB and FAISS for vector storage and search."""

    def __init__(self, db_type: str | None = None):
        self.settings = get_settings()
        self.db_type = db_type or self.settings.VECTOR_DB_TYPE
        self._store = None
        self._init_store()

    def _init_store(self) -> None:
        if self.db_type == "chroma":
            self._init_chroma()
        elif self.db_type == "faiss":
            self._init_faiss()
        else:
            raise ValueError(f"Unsupported vector DB type: {self.db_type}")

    def _init_chroma(self) -> None:
        try:
            import chromadb
            self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                name=self.settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._store = "chroma"
            logger.info(f"ChromaDB initialised: collection '{self.settings.CHROMA_COLLECTION}'")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self._store = None

    def _init_faiss(self) -> None:
        try:
            import faiss
            import numpy as np
            self._faiss_index = None
            self._faiss_docs: list[dict] = []
            self._store = "faiss"
            logger.info("FAISS initialised (in-memory)")
        except ImportError:
            logger.error("faiss-cpu not installed")
            self._store = None

    def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> int:
        """Add documents with their embeddings to the store."""
        if not texts:
            return 0

        doc_ids = ids or [str(uuid.uuid4())[:12] for _ in texts]
        meta = metadatas or [{} for _ in texts]

        if self._store == "chroma":
            self._collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=meta,
                ids=doc_ids,
            )
            logger.info(f"Added {len(texts)} documents to ChromaDB")

        elif self._store == "faiss":
            import faiss
            import numpy as np
            dim = len(embeddings[0])
            if self._faiss_index is None:
                self._faiss_index = faiss.IndexFlatIP(dim)
            vectors = np.array(embeddings, dtype=np.float32)
            self._faiss_index.add(vectors)
            for i, text in enumerate(texts):
                self._faiss_docs.append({
                    "id": doc_ids[i],
                    "text": text,
                    "metadata": meta[i],
                })
            logger.info(f"Added {len(texts)} documents to FAISS")

        return len(texts)

    def search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for the most similar documents."""
        if self._store == "chroma":
            return self._search_chroma(query, query_embedding, n_results)
        elif self._store == "faiss":
            return self._search_faiss(query, query_embedding, n_results)
        logger.warning("No vector store available")
        return []

    def _search_chroma(
        self,
        query: str,
        query_embedding: list[float] | None,
        n_results: int,
    ) -> list[dict]:
        try:
            kwargs: dict[str, Any] = {"n_results": min(n_results, self._collection.count() or 1)}
            if query_embedding:
                kwargs["query_embeddings"] = [query_embedding]
            else:
                kwargs["query_texts"] = [query]

            results = self._collection.query(**kwargs)
            docs = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    score = (
                        1.0 - results["distances"][0][i]
                        if results.get("distances")
                        else 0.0
                    )
                    docs.append({
                        "content": doc,
                        "source": results["metadatas"][0][i].get("source", "unknown")
                        if results.get("metadatas")
                        else "unknown",
                        "score": score,
                        "metadata": results["metadatas"][0][i]
                        if results.get("metadatas")
                        else {},
                    })
            return docs
        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            return []

    def _search_faiss(
        self,
        query: str,
        query_embedding: list[float] | None,
        n_results: int,
    ) -> list[dict]:
        if self._faiss_index is None or not self._faiss_docs:
            return []
        import numpy as np
        if query_embedding is None:
            logger.warning("FAISS requires a query embedding for search")
            return []
        vector = np.array([query_embedding], dtype=np.float32)
        k = min(n_results, len(self._faiss_docs))
        scores, indices = self._faiss_index.search(vector, k)
        docs = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self._faiss_docs):
                doc = self._faiss_docs[idx]
                docs.append({
                    "content": doc["text"],
                    "source": doc["metadata"].get("source", "unknown"),
                    "score": float(score),
                    "metadata": doc["metadata"],
                })
        return docs

    def count(self) -> int:
        if self._store == "chroma":
            return self._collection.count()
        elif self._store == "faiss":
            return len(self._faiss_docs)
        return 0

    def clear(self) -> None:
        if self._store == "chroma":
            self._client.delete_collection(self.settings.CHROMA_COLLECTION)
            self._init_chroma()
        elif self._store == "faiss":
            self._faiss_index = None
            self._faiss_docs = []
