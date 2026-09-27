"""
Report Generator Agent — produces the final structured research report
from the verified answer, claims, evidence, and graph relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import (
    AgentRole,
    AgentMessage,
    Claim,
    ClaimVerdict,
    ComparisonEntry,
    EvidenceChunk,
    ExperimentType,
    GraphRelation,
    ResearchReport,
)


_REPORT_SYSTEM_PROMPT = """\
You are the Report Generator Agent in GraphRAG-MARS.
Your job is to produce a well-structured, professional research report.

The report must contain these sections:
1. Research Question
2. Executive Summary (2-3 paragraphs)
3. Background (context for the question)
4. Findings (key discoveries, numbered)
5. Comparison Table (if comparing methods/approaches)
6. Knowledge Graph Relationships (entity connections found)
7. Evidence (with source citations)
8. Limitations
9. Verified Conclusions (each claim with verification status)
10. References

Format the report using clear section headers.
Be concise but thorough. Every claim must reference its evidence.
"""


class ReportGeneratorAgent(BaseAgent):
    """Generates the final structured research report."""

    def __init__(self, llm=None):
        super().__init__(role=AgentRole.REPORT_GENERATOR, llm=llm)

    def get_system_prompt(self) -> str:
        return _REPORT_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {
            "answer_text": "...",
            "question": "...",
            "verified_claims": [...],
            "evidence_chunks": [...],
            "graph_relations": [...],
            "web_results": [...],
            "fact_check_summary": "...",
            "experiment_type": "multi_agent"
        }
        Output payload: {"report": ResearchReport.model_dump()}
        """
        question = message.payload.get("question", "")
        answer_text = message.payload.get("answer_text", message.content)
        verified_claims_data = message.payload.get("verified_claims", [])
        evidence_chunks_data = message.payload.get("evidence_chunks", [])
        graph_relations_data = message.payload.get("graph_relations", [])
        web_results = message.payload.get("web_results", [])
        experiment_type = message.payload.get("experiment_type", "multi_agent")

        # Build the report using LLM for narrative sections
        narrative = self._generate_narrative(
            question, answer_text, verified_claims_data,
            evidence_chunks_data, graph_relations_data,
        )

        # Parse verified claims
        claims = []
        for c in verified_claims_data:
            try:
                verdict = ClaimVerdict(c.get("verdict", "no_evidence"))
            except ValueError:
                verdict = ClaimVerdict.NO_EVIDENCE
            claims.append(Claim(
                claim_id=c.get("claim_id", str(uuid.uuid4())[:8]),
                text=c.get("text", ""),
                verdict=verdict,
                confidence=c.get("confidence", 0.0),
                reasoning=c.get("reasoning", ""),
            ))

        # Parse evidence
        evidence = [
            EvidenceChunk(**ec) if isinstance(ec, dict) else ec
            for ec in evidence_chunks_data[:20]
        ]

        # Parse graph relations
        relations = [
            GraphRelation(**gr) if isinstance(gr, dict) else gr
            for gr in graph_relations_data[:20]
        ]

        # Build references from web results and evidence sources
        references = self._build_references(web_results, evidence_chunks_data)

        # Extract comparisons from narrative
        comparisons = self._extract_comparisons(narrative)

        # Extract limitations
        limitations = self._extract_limitations(narrative)

        report = ResearchReport(
            report_id=str(uuid.uuid4())[:12],
            research_question=question,
            executive_summary=narrative.get("executive_summary", ""),
            background=narrative.get("background", ""),
            findings=narrative.get("findings", []),
            comparisons=comparisons,
            evidence=evidence,
            graph_relationships=relations,
            limitations=limitations,
            verified_claims=claims,
            references=references,
            generated_at=datetime.now(),
            experiment_type=ExperimentType(experiment_type) if experiment_type in ExperimentType.__members__.values() else ExperimentType.MULTI_AGENT,
        )

        logger.info(f"Report generated: {report.report_id}")

        return self.create_message(
            content="Research report generated successfully",
            payload={"report": report.model_dump()},
        )

    def _generate_narrative(
        self,
        question: str,
        answer: str,
        claims: list[dict],
        evidence: list[dict],
        graph_rels: list[dict],
    ) -> dict:
        """Generate the narrative sections of the report."""
        evidence_summary = "\n".join(
            f"- {e.get('content', '')[:200]} (Source: {e.get('source', 'N/A')})"
            for e in evidence[:10]
        )
        claims_summary = "\n".join(
            f"- {c.get('text', '')} [{c.get('verdict', '?')}]"
            for c in claims[:10]
        )
        graph_summary = "\n".join(
            f"- {g.get('source_entity', '?')} --{g.get('relationship', '?')}--> "
            f"{g.get('target_entity', '?')}"
            for g in graph_rels[:10]
        )

        prompt = (
            f"# Research Question\n{question}\n\n"
            f"# Answer Draft\n{answer}\n\n"
            f"# Evidence\n{evidence_summary}\n\n"
            f"# Verified Claims\n{claims_summary}\n\n"
            f"# Graph Relationships\n{graph_summary}\n\n"
            "Generate a structured research report with these sections as JSON:\n"
            '{"executive_summary": "...", "background": "...", '
            '"findings": [{"title": "...", "content": "..."}], '
            '"limitations": ["..."]}'
        )

        raw = self.call_llm(prompt, temperature=0.3)
        return self._parse_narrative(raw, answer)

    def _parse_narrative(self, raw: str, fallback: str) -> dict:
        import json
        import re
        try:
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            text = json_match.group(1).strip() if json_match else raw.strip()
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            return {
                "executive_summary": fallback[:500],
                "background": "",
                "findings": [{"title": "Answer", "content": fallback}],
                "limitations": ["Report generation used fallback formatting"],
            }

    def _build_references(
        self, web_results: list[dict], evidence_chunks: list[dict]
    ) -> list[dict[str, str]]:
        refs = []
        seen_sources = set()
        for wr in web_results:
            url = wr.get("url", "")
            if url and url not in seen_sources:
                refs.append({"title": wr.get("title", ""), "url": url})
                seen_sources.add(url)
        for ec in evidence_chunks:
            source = ec.get("source", "")
            if source and source not in seen_sources and source != "unknown":
                refs.append({"title": source, "url": ""})
                seen_sources.add(source)
        return refs

    def _extract_comparisons(self, narrative: dict) -> list[ComparisonEntry]:
        """Extract comparison data from findings if present."""
        comparisons = []
        findings = narrative.get("findings", [])
        for f in findings:
            if "compar" in f.get("title", "").lower():
                comparisons.append(ComparisonEntry(
                    dimension=f.get("title", "Comparison"),
                    entries={"details": f.get("content", "")},
                ))
        return comparisons

    def _extract_limitations(self, narrative: dict) -> list[str]:
        return narrative.get("limitations", [])
