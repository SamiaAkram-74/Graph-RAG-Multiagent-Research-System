"""
Basic tests for the GraphRAG-MARS core components.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSchemas:
    """Test Pydantic schema models."""

    def test_research_query(self):
        from src.core.schemas import ResearchQuery, ExperimentType
        query = ResearchQuery(question="Test question")
        assert query.question == "Test question"
        assert query.experiment_type == ExperimentType.MULTI_AGENT

    def test_evidence_chunk(self):
        from src.core.schemas import EvidenceChunk
        chunk = EvidenceChunk(
            chunk_id="test123",
            content="Test content",
            source="test.pdf",
            relevance_score=0.85,
        )
        assert chunk.relevance_score == 0.85
        assert chunk.retrieval_method == "vector"

    def test_claim_verdict(self):
        from src.core.schemas import Claim, ClaimVerdict
        claim = Claim(
            claim_id="c1",
            text="Test claim",
            verdict=ClaimVerdict.SUPPORTED,
            confidence=0.9,
        )
        assert claim.verdict == ClaimVerdict.SUPPORTED

    def test_research_report(self):
        from src.core.schemas import ResearchReport, ExperimentType
        report = ResearchReport(
            report_id="r001",
            research_question="Test?",
            executive_summary="Summary text",
            experiment_type=ExperimentType.HYBRID_RAG,
        )
        assert report.report_id == "r001"
        assert report.experiment_type == ExperimentType.HYBRID_RAG


class TestChunking:
    """Test text chunking."""

    def test_basic_chunking(self):
        from src.rag.chunking import TextChunker
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        chunks = chunker.chunk_document(text, source="test.txt")
        assert len(chunks) >= 1
        assert all(c.source == "test.txt" for c in chunks)

    def test_empty_text(self):
        from src.rag.chunking import TextChunker
        chunker = TextChunker()
        chunks = chunker.chunk_document("", source="empty.txt")
        assert len(chunks) == 0


class TestEvaluation:
    """Test evaluation metrics."""

    def test_precision_at_k(self):
        from src.evaluation.metrics import precision_at_k
        retrieved = ["a", "b", "c", "d", "e"]
        relevant = {"a", "c", "e"}
        assert precision_at_k(retrieved, relevant, k=5) == 0.6

    def test_recall_at_k(self):
        from src.evaluation.metrics import recall_at_k
        retrieved = ["a", "b", "c"]
        relevant = {"a", "c", "d", "e"}
        assert recall_at_k(retrieved, relevant, k=3) == 0.5

    def test_mrr(self):
        from src.evaluation.metrics import mean_reciprocal_rank
        retrieved = ["x", "y", "a", "b"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == 1/3

    def test_hallucination_rate(self):
        from src.evaluation.metrics import hallucination_rate
        claims = [
            {"verdict": "supported"},
            {"verdict": "supported"},
            {"verdict": "unsupported"},
            {"verdict": "contradicted"},
        ]
        assert hallucination_rate(claims) == 0.5


class TestDocumentLoader:
    """Test document loading."""

    def test_load_text_file(self, tmp_path):
        from src.rag.documents import DocumentLoader
        loader = DocumentLoader()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world. This is a test document.")
        doc = loader.load_file(test_file)
        assert "Hello world" in doc["text"]
        assert doc["source"] == "test.txt"

    def test_load_directory(self, tmp_path):
        from src.rag.documents import DocumentLoader
        loader = DocumentLoader()
        (tmp_path / "a.txt").write_text("Doc A")
        (tmp_path / "b.txt").write_text("Doc B")
        docs = loader.load_directory(tmp_path)
        assert len(docs) == 2
