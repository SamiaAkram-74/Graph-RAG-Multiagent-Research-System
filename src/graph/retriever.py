"""
Graph retriever — builds the knowledge graph from documents and provides
query interface for the Graph Retrieval Agent.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from src.graph.entity_extractor import EntityExtractor
from src.graph.graph_store import GraphStore
from src.rag.documents import DocumentLoader
from src.rag.chunking import TextChunker
from src.core.llm import get_llm


class GraphRetriever:
    """Orchestrates knowledge graph construction and retrieval."""

    def __init__(
        self,
        graph_store: GraphStore | None = None,
        entity_extractor: EntityExtractor | None = None,
    ):
        self.graph_store = graph_store or GraphStore(use_neo4j=True)
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.chunker = TextChunker(chunk_size=1024, chunk_overlap=128)
        self.loader = DocumentLoader()

    def build_from_directory(self, dir_path: str) -> dict:
        """Load documents and build the knowledge graph."""
        documents = self.loader.load_directory(dir_path)
        return self.build_from_documents(documents)

    def build_from_file(self, file_path: str) -> dict:
        """Load a single file and add to the knowledge graph."""
        doc = self.loader.load_file(file_path)
        return self.build_from_documents([doc])

    def build_from_documents(self, documents: list[dict]) -> dict:
        """Extract entities/relationships from documents and populate the graph."""
        # Chunk documents for entity extraction (larger chunks)
        chunks = []
        for doc in documents:
            doc_chunks = self.chunker.chunk_document(
                text=doc["text"],
                source=doc.get("source", "unknown"),
            )
            chunks.extend([
                {"text": c.text, "source": c.source}
                for c in doc_chunks
            ])

        if not chunks:
            logger.warning("No chunks for knowledge graph construction")
            return {"entities": 0, "relationships": 0}

        logger.info(f"Extracting entities from {len(chunks)} chunks...")

        # Extract entities and relationships
        extraction_results = self.entity_extractor.extract_batch(chunks)

        # Aggregate all entities and relationships
        all_entities: list[dict] = []
        all_relationships: list[dict] = []

        for result in extraction_results:
            all_entities.extend(result.get("entities", []))
            all_relationships.extend(result.get("relationships", []))

        # Deduplicate entities by name
        seen = set()
        unique_entities = []
        for e in all_entities:
            name = e.get("name", "").lower()
            if name and name not in seen:
                seen.add(name)
                unique_entities.append(e)

        # Add to graph
        entities_added = self.graph_store.add_entities(unique_entities)
        rels_added = self.graph_store.add_relationships(all_relationships)

        counts = self.graph_store.count()
        logger.info(
            f"Knowledge graph: {counts['entities']} entities, "
            f"{counts['relationships']} relationships"
        )

        return {
            "entities": entities_added,
            "relationships": rels_added,
            "total_entities": counts["entities"],
            "total_relationships": counts["relationships"],
        }

    def query(
        self,
        entities: list[str],
        hop_depth: int = 2,
        relationship_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query the knowledge graph for relationships around entities."""
        return self.graph_store.query_entities(
            entities=entities,
            hop_depth=hop_depth,
            relationship_types=relationship_types,
            limit=limit,
        )

    def get_entity_context(
        self, entities: list[str], limit: int = 10
    ) -> list[dict]:
        """Get contextual text for entities from the graph."""
        return self.graph_store.get_entity_context(entities=entities, limit=limit)

    def get_graph_summary(self) -> dict:
        """Return a summary of the knowledge graph."""
        counts = self.graph_store.count()
        entities = self.graph_store.get_all_entities()[:20]
        relationships = self.graph_store.get_all_relationships()[:20]
        return {
            "total_entities": counts["entities"],
            "total_relationships": counts["relationships"],
            "sample_entities": entities,
            "sample_relationships": relationships,
        }
