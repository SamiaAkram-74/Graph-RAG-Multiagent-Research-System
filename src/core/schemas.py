"""
Pydantic schemas used across all agents and components.
Provides type-safe data models for queries, evidence, claims, and reports.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class AgentRole(str, Enum):
    PLANNER = "planner"
    VECTOR_RETRIEVAL = "vector_retrieval"
    GRAPH_RETRIEVAL = "graph_retrieval"
    WEB_RESEARCH = "web_research"
    REASONING = "reasoning"
    FACT_CHECKER = "fact_checker"
    REPORT_GENERATOR = "report_generator"


class ClaimVerdict(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    NO_EVIDENCE = "no_evidence"


class ExperimentType(str, Enum):
    BASELINE_LLM = "baseline_llm"
    VECTOR_RAG = "vector_rag"
    GRAPH_RAG = "graph_rag"
    HYBRID_RAG = "hybrid_rag"
    MULTI_AGENT = "multi_agent"


# ── Query Models ─────────────────────────────────────────────────────────────

class ResearchQuery(BaseModel):
    """A user-submitted research question."""
    question: str
    experiment_type: ExperimentType = ExperimentType.MULTI_AGENT
    include_web_search: bool = True
    max_results: int = 10
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubQuestion(BaseModel):
    """A decomposed sub-question produced by the Planner Agent."""
    id: str
    question: str
    required_agents: list[AgentRole]
    priority: int = 1
    dependencies: list[str] = Field(default_factory=list)


# ── Evidence Models ──────────────────────────────────────────────────────────

class EvidenceChunk(BaseModel):
    """A single piece of retrieved evidence."""
    chunk_id: str
    content: str
    source: str
    relevance_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_method: str = "vector"  # vector | graph | web


class GraphRelation(BaseModel):
    """A relationship retrieved from the knowledge graph."""
    source_entity: str
    relationship: str
    target_entity: str
    source_document: Optional[str] = None
    weight: float = 1.0


class WebResult(BaseModel):
    """A result from web search."""
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float = 0.0


# ── Claim & Verification ─────────────────────────────────────────────────────

class Claim(BaseModel):
    """A factual claim extracted from generated text."""
    claim_id: str
    text: str
    supporting_evidence: list[EvidenceChunk] = Field(default_factory=list)
    verdict: ClaimVerdict = ClaimVerdict.NO_EVIDENCE
    confidence: float = 0.0
    reasoning: str = ""


# ── Agent Communication ──────────────────────────────────────────────────────

class AgentMessage(BaseModel):
    """Message exchanged between agents."""
    sender: AgentRole
    receiver: Optional[AgentRole] = None
    content: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskPlan(BaseModel):
    """Execution plan produced by the Planner Agent."""
    original_question: str
    sub_questions: list[SubQuestion]
    execution_order: list[str]  # sub-question IDs in order
    estimated_complexity: str = "medium"  # low | medium | high


# ── Report Models ────────────────────────────────────────────────────────────

class ComparisonEntry(BaseModel):
    """A single comparison dimension."""
    dimension: str
    entries: dict[str, str]  # method -> value


class ResearchReport(BaseModel):
    """The final structured research report."""
    report_id: str
    research_question: str
    executive_summary: str
    background: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)
    comparisons: list[ComparisonEntry] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    graph_relationships: list[GraphRelation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    verified_claims: list[Claim] = Field(default_factory=list)
    references: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.now)
    experiment_type: ExperimentType = ExperimentType.MULTI_AGENT


# ── Evaluation Models ────────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    """Results of evaluating a single experiment."""
    experiment_type: ExperimentType
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    factual_correctness: float = 0.0
    faithfulness: float = 0.0
    relevance: float = 0.0
    completeness: float = 0.0
    hallucination_rate: float = 0.0
    response_latency_sec: float = 0.0
    token_usage: int = 0
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
