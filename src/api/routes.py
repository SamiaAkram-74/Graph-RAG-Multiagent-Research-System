"""
API routes — all REST endpoints for document ingestion, querying,
evaluation, and system status.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from loguru import logger

from src.config import get_settings
from src.core.schemas import (
    AgentMessage,
    AgentRole,
    ExperimentType,
    ResearchQuery,
    ResearchReport,
)

router = APIRouter()

# ── Lazy-initialised services ────────────────────────────────────────────────

_rag_pipeline = None
_graph_retriever = None
_agents = None


def _get_rag_pipeline():
    global _rag_pipeline
    if _rag_pipeline is None:
        from src.rag.pipeline import RAGPipeline
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def _get_graph_retriever():
    global _graph_retriever
    if _graph_retriever is None:
        from src.graph.retriever import GraphRetriever
        _graph_retriever = GraphRetriever()
    return _graph_retriever


def _get_agents():
    """Initialise all agents on first use."""
    global _agents
    if _agents is None:
        from src.agents.planner_agent import PlannerAgent
        from src.agents.vector_agent import VectorRetrievalAgent
        from src.agents.graph_agent import GraphRetrievalAgent
        from src.agents.web_agent import WebResearchAgent
        from src.agents.reasoning_agent import ReasoningAgent
        from src.agents.fact_checker_agent import FactCheckerAgent
        from src.agents.report_agent import ReportGeneratorAgent

        rag = _get_rag_pipeline()
        graph = _get_graph_retriever()

        _agents = {
            AgentRole.PLANNER: PlannerAgent(),
            AgentRole.VECTOR_RETRIEVAL: VectorRetrievalAgent(vector_store=rag.vector_store),
            AgentRole.GRAPH_RETRIEVAL: GraphRetrievalAgent(graph_store=graph.graph_store),
            AgentRole.WEB_RESEARCH: WebResearchAgent(),
            AgentRole.REASONING: ReasoningAgent(),
            AgentRole.FACT_CHECKER: FactCheckerAgent(),
            AgentRole.REPORT_GENERATOR: ReportGeneratorAgent(),
        }
    return _agents


# ── Request/Response Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    experiment_type: str = "multi_agent"
    include_web_search: bool = True
    max_results: int = 10


class QueryResponse(BaseModel):
    report_id: str
    research_question: str
    executive_summary: str
    findings: list[dict] = []
    evidence_count: int = 0
    graph_relations_count: int = 0
    verified_claims: list[dict] = []
    limitations: list[str] = []
    references: list[dict] = []
    experiment_type: str
    latency_sec: float = 0.0


class IngestResponse(BaseModel):
    message: str
    documents: int = 0
    chunks: int = 0
    indexed: int = 0


class GraphBuildResponse(BaseModel):
    message: str
    entities: int = 0
    relationships: int = 0


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def system_status():
    """Return system status and component health."""
    rag = _get_rag_pipeline()
    graph = _get_graph_retriever()
    agents = _get_agents()

    return {
        "status": "operational",
        "vector_store": {
            "type": rag.vector_store.db_type,
            "document_count": rag.vector_store.count(),
        },
        "knowledge_graph": graph.get_graph_summary(),
        "agents": [role.value for role in agents.keys()],
    }


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest_documents(file: UploadFile = File(...)):
    """Upload and ingest a document into the vector store and knowledge graph."""
    settings = get_settings()
    docs_dir = settings.DOCS_DIR
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    file_path = docs_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    # Ingest into vector store
    rag = _get_rag_pipeline()
    result = rag.ingest_file(file_path)

    return IngestResponse(
        message=f"Document '{file.filename}' ingested successfully",
        documents=result.get("documents", 0),
        chunks=result.get("chunks", 0),
        indexed=result.get("indexed", 0),
    )


@router.post("/documents/ingest-directory")
async def ingest_directory(dir_path: str = Form(...)):
    """Ingest all documents from a directory."""
    rag = _get_rag_pipeline()
    result = rag.ingest_directory(dir_path)
    return {
        "message": f"Ingested documents from {dir_path}",
        **result,
    }


@router.post("/graph/build")
async def build_knowledge_graph(dir_path: str = Form(...)):
    """Build the knowledge graph from documents in a directory."""
    graph = _get_graph_retriever()
    result = graph.build_from_directory(dir_path)
    return GraphBuildResponse(
        message="Knowledge graph built successfully",
        entities=result.get("entities", 0),
        relationships=result.get("relationships", 0),
    )


@router.get("/graph/summary")
async def graph_summary():
    """Return a summary of the knowledge graph."""
    graph = _get_graph_retriever()
    return graph.get_graph_summary()


@router.post("/query", response_model=QueryResponse)
async def query_system(request: QueryRequest):
    """Run a research query through the multi-agent pipeline."""
    start_time = time.time()
    agents = _get_agents()
    rag = _get_rag_pipeline()
    graph = _get_graph_retriever()

    exp_type = ExperimentType(request.experiment_type)
    question = request.question

    # Collect evidence from all sources
    all_evidence: list[dict] = []
    all_graph_relations: list[dict] = []
    all_web_results: list[dict] = []

    if exp_type == ExperimentType.BASELINE_LLM:
        # Baseline: just use LLM directly
        from src.core.llm import get_llm
        llm = get_llm()
        answer = llm.generate(question)
        all_evidence = []

    elif exp_type == ExperimentType.VECTOR_RAG:
        # Vector RAG only
        results = rag.query(question, n_results=request.max_results)
        all_evidence = results
        answer = ""

    elif exp_type == ExperimentType.GRAPH_RAG:
        # Graph RAG only
        graph_msg = AgentMessage(
            sender=AgentRole.PLANNER,
            content=question,
            payload={"query": question, "max_results": request.max_results},
        )
        graph_response = agents[AgentRole.GRAPH_RETRIEVAL].execute(graph_msg)
        all_evidence = graph_response.payload.get("evidence_chunks", [])
        all_graph_relations = graph_response.payload.get("graph_relations", [])
        answer = ""

    elif exp_type in (ExperimentType.HYBRID_RAG, ExperimentType.MULTI_AGENT):
        # Full multi-agent pipeline
        # Step 1: Planning
        plan_msg = AgentMessage(
            sender=AgentRole.PLANNER,
            content=question,
            payload={
                "question": question,
                "include_web_search": request.include_web_search,
            },
        )
        plan_response = agents[AgentRole.PLANNER].execute(plan_msg)

        # Step 2: Vector retrieval
        vector_msg = AgentMessage(
            sender=AgentRole.PLANNER,
            content=question,
            payload={"query": question, "max_results": request.max_results},
        )
        vector_response = agents[AgentRole.VECTOR_RETRIEVAL].execute(vector_msg)
        all_evidence.extend(vector_response.payload.get("evidence_chunks", []))

        # Step 3: Graph retrieval
        graph_msg = AgentMessage(
            sender=AgentRole.PLANNER,
            content=question,
            payload={"query": question, "max_results": request.max_results},
        )
        graph_response = agents[AgentRole.GRAPH_RETRIEVAL].execute(graph_msg)
        all_evidence.extend(graph_response.payload.get("evidence_chunks", []))
        all_graph_relations = graph_response.payload.get("graph_relations", [])

        # Step 4: Web search
        if request.include_web_search:
            web_msg = AgentMessage(
                sender=AgentRole.PLANNER,
                content=question,
                payload={"query": question, "max_results": 5},
            )
            web_response = agents[AgentRole.WEB_RESEARCH].execute(web_msg)
            all_evidence.extend(web_response.payload.get("evidence_chunks", []))
            all_web_results = web_response.payload.get("web_results", [])

        answer = ""

    # Step 5: Reasoning (for all except baseline)
    if exp_type != ExperimentType.BASELINE_LLM:
        reasoning_msg = AgentMessage(
            sender=AgentRole.PLANNER,
            content=question,
            payload={
                "question": question,
                "evidence_chunks": all_evidence,
                "graph_relations": all_graph_relations,
                "web_results": all_web_results,
            },
        )
        reasoning_response = agents[AgentRole.REASONING].execute(reasoning_msg)
        answer = reasoning_response.payload.get("reasoned_answer", "")

        # Step 6: Fact checking
        fact_msg = AgentMessage(
            sender=AgentRole.REASONING,
            content=answer,
            payload={
                "reasoned_answer": answer,
                "question": question,
                "evidence_chunks": all_evidence,
                "evidence_used": len(all_evidence),
            },
        )
        fact_response = agents[AgentRole.FACT_CHECKER].execute(fact_msg)
        verified_claims = fact_response.payload.get("verified_claims", [])
    else:
        verified_claims = []
        fact_response = None

    # Step 7: Report generation
    report_msg = AgentMessage(
        sender=AgentRole.FACT_CHECKER,
        content=answer,
        payload={
            "answer_text": answer,
            "question": question,
            "verified_claims": verified_claims,
            "evidence_chunks": all_evidence,
            "graph_relations": all_graph_relations,
            "web_results": all_web_results,
            "fact_check_summary": fact_response.payload.get("fact_check_summary", "") if fact_response else "",
            "experiment_type": request.experiment_type,
        },
    )
    report_response = agents[AgentRole.REPORT_GENERATOR].execute(report_msg)
    report_data = report_response.payload.get("report", {})

    latency = time.time() - start_time

    return QueryResponse(
        report_id=report_data.get("report_id", str(uuid.uuid4())[:12]),
        research_question=question,
        executive_summary=report_data.get("executive_summary", ""),
        findings=report_data.get("findings", []),
        evidence_count=len(all_evidence),
        graph_relations_count=len(all_graph_relations),
        verified_claims=verified_claims,
        limitations=report_data.get("limitations", []),
        references=report_data.get("references", []),
        experiment_type=request.experiment_type,
        latency_sec=round(latency, 2),
    )


@router.post("/evaluate/run")
async def run_evaluation():
    """Run the evaluation benchmark suite."""
    from src.evaluation.metrics import EvaluationRunner
    runner = EvaluationRunner()
    results = runner.run_all_experiments()
    return {"message": "Evaluation complete", "results": results}


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Retrieve a saved report (placeholder — stores in memory)."""
    raise HTTPException(status_code=404, detail="Report storage not yet implemented")
