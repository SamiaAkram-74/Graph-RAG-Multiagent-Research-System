"""
Embeddings — generates vector embeddings for text chunks using
sentence-transformers.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from loguru import logger

from src.config import get_settings


class EmbeddingModel:
    """Wraps sentence-transformers for text embedding."""

    def __init__(self, model_name: str | None = None):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.EMBEDDING_MODEL
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"Embedding model loaded: {self.model_name}")
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string, returns a vector."""
        model = self._load_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a batch (more efficient)."""
        if not texts:
            return []
        model = self._load_model()
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=64)
        return [emb.tolist() for emb in embeddings]

    def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    @property
    def dimension(self) -> int:
        return self.settings.EMBEDDING_DIMENSION


def get_embedding_model(model_name: str | None = None) -> EmbeddingModel:
    return EmbeddingModel(model_name=model_name)
