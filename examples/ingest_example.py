"""
Example: Ingest sample documents and build both vector store and knowledge graph.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src.rag.pipeline import RAGPipeline
from src.graph.retriever import GraphRetriever


def main():
    logger.info("=" * 60)
    logger.info("GraphRAG-MARS — Ingestion Example")
    logger.info("=" * 60)

    # ── Step 1: Ingest documents into vector store ─────────────────────
    logger.info("\n[Step 1] Ingesting documents into vector store...")
    rag = RAGPipeline()

    docs_dir = os.path.join(os.path.dirname(__file__), "..", "data", "documents")
    if os.path.exists(docs_dir) and os.listdir(docs_dir):
        result = rag.ingest_directory(docs_dir)
        logger.info(f"Vector store: {result}")
    else:
        logger.warning(f"No documents found in {docs_dir}")
        logger.info("Place PDF, TXT, or DOCX files in data/documents/ and re-run.")

        # Demo with inline text
        demo_docs = [{
            "text": (
                "Climate change causes temperature increases which lead to water stress "
                "in agricultural regions. Water stress reduces crop growth and ultimately "
                "decreases crop yield. Studies show that for every 1°C increase in temperature, "
                "wheat yield decreases by approximately 6%. Adaptation strategies include "
                "drought-resistant crop varieties and improved irrigation systems."
            ),
            "source": "demo_climate_agriculture.txt",
            "path": "demo",
            "extension": ".txt",
        }, {
            "text": (
                "Convolutional Neural Networks (CNNs) have been the dominant approach for "
                "medical image classification. They use convolutional layers to extract local "
                "features effectively. Vision Transformers (ViT) apply self-attention mechanisms "
                "to capture global context in images. Recent hybrid models combine CNN feature "
                "extraction with transformer attention for improved performance on medical "
                "imaging tasks such as X-ray and histopathology classification."
            ),
            "source": "demo_medical_imaging.txt",
            "path": "demo",
            "extension": ".txt",
        }]
        result = rag.ingest_documents(demo_docs)
        logger.info(f"Demo ingestion: {result}")

    # ── Step 2: Build knowledge graph ──────────────────────────────────
    logger.info("\n[Step 2] Building knowledge graph...")
    graph = GraphRetriever()

    if os.path.exists(docs_dir) and os.listdir(docs_dir):
        graph_result = graph.build_from_directory(docs_dir)
    else:
        logger.info("Building graph from demo documents...")
        graph_result = graph.build_from_documents(demo_docs)

    logger.info(f"Knowledge graph: {graph_result}")

    # ── Step 3: Test retrieval ─────────────────────────────────────────
    logger.info("\n[Step 3] Testing retrieval...")

    test_queries = [
        "How does climate change affect crop yield?",
        "Compare CNN and Vision Transformer for medical imaging",
    ]

    for query in test_queries:
        logger.info(f"\nQuery: {query}")
        # Vector search
        vector_results = rag.query(query, n_results=3)
        logger.info(f"  Vector results: {len(vector_results)}")
        for r in vector_results[:2]:
            logger.info(f"    [{r.get('score', 0):.3f}] {r.get('content', '')[:100]}...")

        # Graph search
        summary = graph.get_graph_summary()
        logger.info(f"  Graph: {summary['total_entities']} entities, "
                     f"{summary['total_relationships']} relationships")

    logger.info("\n✅ Ingestion example complete!")


if __name__ == "__main__":
    main()
