"""
Example: Run a research query through the full multi-agent pipeline
and display the structured report.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src.core.schemas import AgentMessage, AgentRole
from src.agents.planner_agent import PlannerAgent
from src.agents.vector_agent import VectorRetrievalAgent
from src.agents.graph_agent import GraphRetrievalAgent
from src.agents.web_agent import WebResearchAgent
from src.agents.reasoning_agent import ReasoningAgent
from src.agents.fact_checker_agent import FactCheckerAgent
from src.agents.report_agent import ReportGeneratorAgent
from src.rag.pipeline import RAGPipeline
from src.graph.retriever import GraphRetriever


def run_query(question: str, include_web: bool = True):
    """Run the full multi-agent research pipeline."""
    logger.info("=" * 60)
    logger.info(f"Research Question: {question}")
    logger.info("=" * 60)

    # Initialise components
    rag = RAGPipeline()
    graph = GraphRetriever()

    # Initialise agents
    planner = PlannerAgent()
    vector_agent = VectorRetrievalAgent(vector_store=rag.vector_store)
    graph_agent = GraphRetrievalAgent(graph_store=graph.graph_store)
    web_agent = WebResearchAgent()
    reasoning = ReasoningAgent()
    fact_checker = FactCheckerAgent()
    report_gen = ReportGeneratorAgent()

    # ── Step 1: Planning ───────────────────────────────────────────────
    logger.info("\n[1/7] Planning...")
    plan_msg = AgentMessage(
        sender=AgentRole.PLANNER,
        content=question,
        payload={"question": question, "include_web_search": include_web},
    )
    plan_response = planner.execute(plan_msg)
    task_plan = plan_response.payload.get("task_plan", {})
    logger.info(f"  Created {len(task_plan.get('sub_questions', []))} sub-questions")

    # ── Step 2: Vector Retrieval ───────────────────────────────────────
    logger.info("\n[2/7] Vector Retrieval...")
    vector_msg = AgentMessage(
        sender=AgentRole.PLANNER,
        content=question,
        payload={"query": question, "max_results": 10},
    )
    vector_response = vector_agent.execute(vector_msg)
    all_evidence = vector_response.payload.get("evidence_chunks", [])
    logger.info(f"  Retrieved {len(all_evidence)} chunks")

    # ── Step 3: Graph Retrieval ────────────────────────────────────────
    logger.info("\n[3/7] Graph Retrieval...")
    graph_msg = AgentMessage(
        sender=AgentRole.PLANNER,
        content=question,
        payload={"query": question, "max_results": 10},
    )
    graph_response = graph_agent.execute(graph_msg)
    all_evidence.extend(graph_response.payload.get("evidence_chunks", []))
    all_relations = graph_response.payload.get("graph_relations", [])
    logger.info(f"  Retrieved {len(all_relations)} relations")

    # ── Step 4: Web Research ───────────────────────────────────────────
    all_web = []
    if include_web:
        logger.info("\n[4/7] Web Research...")
        web_msg = AgentMessage(
            sender=AgentRole.PLANNER,
            content=question,
            payload={"query": question, "max_results": 5},
        )
        web_response = web_agent.execute(web_msg)
        all_evidence.extend(web_response.payload.get("evidence_chunks", []))
        all_web = web_response.payload.get("web_results", [])
        logger.info(f"  Found {len(all_web)} web results")
    else:
        logger.info("\n[4/7] Web Research skipped")

    # ── Step 5: Reasoning ──────────────────────────────────────────────
    logger.info("\n[5/7] Reasoning...")
    reasoning_msg = AgentMessage(
        sender=AgentRole.PLANNER,
        content=question,
        payload={
            "question": question,
            "evidence_chunks": all_evidence,
            "graph_relations": all_relations,
            "web_results": all_web,
        },
    )
    reasoning_response = reasoning.execute(reasoning_msg)
    answer = reasoning_response.payload.get("reasoned_answer", "")
    logger.info(f"  Generated {len(answer)} chars of reasoning")

    # ── Step 6: Fact Checking ──────────────────────────────────────────
    logger.info("\n[6/7] Fact Checking...")
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
    fact_response = fact_checker.execute(fact_msg)
    verified_claims = fact_response.payload.get("verified_claims", [])
    logger.info(f"  Verified {len(verified_claims)} claims")

    # ── Step 7: Report Generation ──────────────────────────────────────
    logger.info("\n[7/7] Report Generation...")
    report_msg = AgentMessage(
        sender=AgentRole.FACT_CHECKER,
        content=answer,
        payload={
            "answer_text": answer,
            "question": question,
            "verified_claims": verified_claims,
            "evidence_chunks": all_evidence,
            "graph_relations": all_relations,
            "web_results": all_web,
            "fact_check_summary": fact_response.payload.get("fact_check_summary", ""),
            "experiment_type": "multi_agent",
        },
    )
    report_response = report_gen.execute(report_msg)
    report = report_response.payload.get("report", {})

    # ── Display Report ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("AI RESEARCH REPORT")
    print("=" * 60)
    print(f"\nResearch Question:\n{report.get('research_question', '')}")
    print(f"\n{'─' * 60}")
    print("EXECUTIVE SUMMARY")
    print(f"{'─' * 60}")
    print(report.get("executive_summary", "N/A"))

    findings = report.get("findings", [])
    if findings:
        print(f"\n{'─' * 60}")
        print("FINDINGS")
        print(f"{'─' * 60}")
        for i, f in enumerate(findings, 1):
            print(f"\n{i}. {f.get('title', 'Finding')}")
            print(f"   {f.get('content', '')}")

    claims = report.get("verified_claims", [])
    if claims:
        print(f"\n{'─' * 60}")
        print("VERIFIED CONCLUSIONS")
        print(f"{'─' * 60}")
        for c in claims:
            icon = "✅" if c.get("verdict") == "supported" else "⚠️"
            print(f"{icon} {c.get('text', '')} [{c.get('verdict', '')}]")

    print(f"\n{'=' * 60}")
    print(f"Report ID: {report.get('report_id', 'N/A')}")

    return report


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else (
        "How does climate change affect crop yield through water stress?"
    )
    run_query(question)
