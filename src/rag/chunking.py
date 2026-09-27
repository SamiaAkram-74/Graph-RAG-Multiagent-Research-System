"""
Text chunking — splits documents into overlapping chunks suitable for
embedding and vector storage.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from loguru import logger

from src.config import get_settings


@dataclass
class Chunk:
    """A single text chunk with metadata."""
    chunk_id: str
    text: str
    source: str
    chunk_index: int
    start_char: int = 0
    end_char: int = 0
    metadata: dict = field(default_factory=dict)


class TextChunker:
    """Splits text into overlapping chunks respecting sentence boundaries."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        settings = get_settings()
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def chunk_document(
        self,
        text: str,
        source: str = "unknown",
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Split a document into overlapping chunks."""
        if not text.strip():
            return []

        # Split into sentences first
        sentences = self._split_sentences(text)
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_length = 0
        char_offset = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # If adding this sentence exceeds chunk size, finalise current chunk
            if current_length + sentence_len > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4())[:12],
                    text=chunk_text,
                    source=source,
                    chunk_index=len(chunks),
                    start_char=char_offset,
                    end_char=char_offset + len(chunk_text),
                    metadata=metadata or {},
                ))

                # Keep overlap: retain last few sentences
                overlap_text = ""
                overlap_sentences = []
                for s in reversed(current_chunk):
                    if len(overlap_text) + len(s) <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_text = " ".join(overlap_sentences)
                    else:
                        break
                current_chunk = overlap_sentences
                current_length = len(" ".join(current_chunk))
                char_offset += len(chunk_text) - len(" ".join(current_chunk))

            current_chunk.append(sentence)
            current_length += sentence_len + 1  # +1 for space

        # Handle remaining text
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4())[:12],
                text=chunk_text,
                source=source,
                chunk_index=len(chunks),
                start_char=char_offset,
                end_char=char_offset + len(chunk_text),
                metadata=metadata or {},
            ))

        logger.debug(f"Chunked '{source}': {len(chunks)} chunks (size={self.chunk_size})")
        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences, preserving content."""
        # Simple sentence splitting regex
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]
