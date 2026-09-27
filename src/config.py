"""
Global configuration for GraphRAG-MARS.
All settings loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


class Settings(BaseSettings):
    """Centralised application settings."""

    # ── Application ───────────────────────────────────────────────────
    APP_NAME: str = "GraphRAG-MARS"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ── LLM ───────────────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(default="gemini", description="gemini or openai")
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    TEMPERATURE: float = 0.2

    # ── Embeddings ────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # ── Vector Database ───────────────────────────────────────────────
    VECTOR_DB_TYPE: str = Field(default="chroma", description="chroma or faiss")
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "graphrag_docs"
    FAISS_INDEX_PATH: str = "./data/faiss_index"

    # ── Knowledge Graph ───────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # ── Web Search ────────────────────────────────────────────────────
    SERPER_API_KEY: str = ""
    DUCKDUCKGO_ENABLED: bool = True

    # ── Document Processing ───────────────────────────────────────────
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── Evaluation ────────────────────────────────────────────────────
    BENCHMARK_DATASET_PATH: str = "./data/benchmarks/"
    EVAL_RESULTS_PATH: str = "./data/eval_results/"

    # ── Paths ─────────────────────────────────────────────────────────
    DATA_DIR: Path = Field(default_factory=lambda: _project_root / "data")
    DOCS_DIR: Path = Field(default_factory=lambda: _project_root / "data" / "documents")

    class Config:
        env_file = str(_project_root / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
