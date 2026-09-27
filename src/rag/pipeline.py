"""
RAG Pipeline — orchestrates document loading, chunking, embedding,
and indexing into the vector store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from src.rag.documents import DocumentLoader
from src.rag.chunking import TextChunker, Chunk
from src.rag.embeddings import EmbeddingModel, get_embedding_model
from src.rag.vector_store import VectorStore


class RAGPipeline:
    """End-to-end pipeline for ingesting documents into the vector store."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedding_model: EmbeddingModel | None = None,
        chunker: TextChunker | None = None,
    ):
        self.loader = DocumentLoader()
        self.chunker = chunker or TextChunker()
        self.embedding_model = embedding_model or get_embedding_model()
        self.vector_store = vector_store or VectorStore()

    def ingest_directory(self, dir_path: str | Path) -> dict:
        """Load, chunk, embed, and index all documents in a directory."""
        documents = self.loader.load_directory(dir_path)
        return self.ingest_documents(documents)

    def ingest_file(self, file_path: str | Path) -> dict:
        """Load, chunk, embed, and index a single file."""
        doc = self.loader.load_file(file_path)
        return self.ingest_documents([doc])

    def ingest_documents(self, documents: list[dict]) -> dict:
        """Process a list of document dicts through the full pipeline."""
        all_chunks: list[Chunk] = []

        # Step 1: Chunk documents
        for doc in documents:
            chunks = self.chunker.chunk_document(
                text=doc["text"],
                source=doc.get("source", "unknown"),
                metadata={
                    "path": doc.get("path", ""),
                    "extension": doc.get("extension", ""),
                },
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning("No chunks generated from documents")
            return {"documents": len(documents), "chunks": 0, "indexed": 0}

        logger.info(f"Generated {len(all_chunks)} chunks from {len(documents)} documents")

        # Step 2: Generate embeddings in batches
        texts = [chunk.text for chunk in all_chunks]
        embeddings = self.embedding_model.embed_batch(texts)

        # Step 3: Index into vector store
        metadatas = [
            {"source": chunk.source, "chunk_id": chunk.chunk_id, "chunk_index": chunk.chunk_index}
            for chunk in all_chunks
        ]
        ids = [chunk.chunk_id for chunk in all_chunks]

        indexed = self.vector_store.add_documents(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Indexed {indexed} chunks into vector store")
        return {
            "documents": len(documents),
            "chunks": len(all_chunks),
            "indexed": indexed,
        }

    def query(
        self,
        question: str,
        n_results: int = 10,
    ) -> list[dict]:
        """Query the pipeline: embed question and search vector store."""
        query_embedding = self.embedding_model.embed_text(question)
        return self.vector_store.search(
            query=question,
            query_embedding=query_embedding,
            n_results=n_results,
        )
