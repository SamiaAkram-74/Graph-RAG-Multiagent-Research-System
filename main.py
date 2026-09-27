"""
GraphRAG-MARS — Main entry point.
Run the FastAPI server, ingest documents, or run evaluation from CLI.
"""

from __future__ import annotations

import sys
import argparse

from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    """Configure loguru logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
    )


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the FastAPI server."""
    import uvicorn
    logger.info(f"Starting GraphRAG-MARS server on {host}:{port}")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=True)


def ingest_documents(path: str) -> None:
    """Ingest documents from a path into the vector store."""
    from src.rag.pipeline import RAGPipeline
    pipeline = RAGPipeline()

    import os
    if os.path.isdir(path):
        result = pipeline.ingest_directory(path)
    else:
        result = pipeline.ingest_file(path)

    logger.info(f"Ingestion complete: {result}")


def build_graph(path: str) -> None:
    """Build knowledge graph from documents."""
    from src.graph.retriever import GraphRetriever
    retriever = GraphRetriever()

    import os
    if os.path.isdir(path):
        result = retriever.build_from_directory(path)
    else:
        result = retriever.build_from_file(path)

    logger.info(f"Graph build complete: {result}")


def run_evaluation() -> None:
    """Run the evaluation benchmark suite."""
    from src.evaluation.metrics import EvaluationRunner
    runner = EvaluationRunner()
    results = runner.run_all_experiments()
    table = runner.generate_comparison_table(results)
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print("=" * 80)
    print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAG-MARS — Multi-Agent Research System")
    subparsers = parser.add_subparsers(dest="command")

    # Server
    server_parser = subparsers.add_parser("serve", help="Start the API server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    server_parser.add_argument("--port", type=int, default=8080, help="Port to bind")

    # Ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
    ingest_parser.add_argument("path", help="Path to file or directory")

    # Graph
    graph_parser = subparsers.add_parser("graph", help="Build knowledge graph")
    graph_parser.add_argument("path", help="Path to file or directory")

    # Evaluate
    subparsers.add_parser("evaluate", help="Run evaluation benchmarks")

    # Log level
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()
    setup_logging(args.log_level)

    if args.command == "serve":
        run_server(args.host, args.port)
    elif args.command == "ingest":
        ingest_documents(args.path)
    elif args.command == "graph":
        build_graph(args.path)
    elif args.command == "evaluate":
        run_evaluation()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
