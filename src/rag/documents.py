"""
Document loader — loads and extracts text from various document formats
(PDF, DOCX, TXT, Markdown).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from loguru import logger


class DocumentLoader:
    """Loads documents from various file formats and yields text + metadata."""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv"}

    def load_file(self, file_path: str | Path) -> dict:
        """Load a single file and return its text content and metadata."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            text = self._load_pdf(path)
        elif ext == ".docx":
            text = self._load_docx(path)
        elif ext in (".txt", ".md", ".csv"):
            text = self._load_text(path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        return {
            "text": text,
            "source": str(path.name),
            "path": str(path),
            "extension": ext,
            "size_bytes": path.stat().st_size,
        }

    def load_directory(self, dir_path: str | Path) -> list[dict]:
        """Load all supported documents from a directory."""
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        documents = []
        for ext in self.SUPPORTED_EXTENSIONS:
            for file_path in sorted(dir_path.glob(f"**/*{ext}")):
                try:
                    doc = self.load_file(file_path)
                    documents.append(doc)
                    logger.info(f"Loaded: {file_path.name} ({len(doc['text'])} chars)")
                except Exception as e:
                    logger.error(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(documents)} documents from {dir_path}")
        return documents

    def _load_pdf(self, path: Path) -> str:
        """Extract text from a PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("PyMuPDF not installed, trying pdfplumber")
            return self._load_pdf_plumber(path)

    def _load_pdf_plumber(self, path: Path) -> str:
        """Fallback PDF loader using pdfplumber."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            return "\n\n".join(text_parts)
        except ImportError:
            raise ImportError("Install pymupdf or pdfplumber for PDF support")

    def _load_docx(self, path: Path) -> str:
        """Extract text from a DOCX file."""
        try:
            from docx import Document
            doc = Document(str(path))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise ImportError("Install python-docx for DOCX support")

    def _load_text(self, path: Path) -> str:
        """Load a plain text file."""
        return path.read_text(encoding="utf-8", errors="replace")
