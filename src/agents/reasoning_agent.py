"""
Reasoning Agent — combines evidence from vector, graph, and web retrieval,
then reasons over the collected evidence to produce an answer draft.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import AgentRole, AgentMessage


_REASONING_SYSTEM_PROMPT = """\
You are the Reasoning Agent in a multi-agent research system called GraphRAG-MARS.
Your job is to synthesise evidence from multiple sources and produce a
well-reasoned, evidence-grounded answer.

Rules:
1. ONLY use the provided evidence. Do NOT invent information.
2. When evidence conflicts, note the disagreement.
3. Cite sources by their identifiers.
4. Structure your reasoning step-by-step.
5. If evidence is insufficient for a sub-question, say so explicitly.

You will receive:
- The original research question
- Evidence chunks from vector search (semantic similarity)
- Graph relationships (entity connections)
- Web search results (current information)

Produce a structured answer with clear reasoning and citations.
"""


class ReasoningAgent(BaseAgent):
    """Synthesises evidence and produces a reasoned answer."""

    def __init__(self, llm=None):
        super().__init__(role=AgentRole.REASONING, llm=llm)

    def get_system_prompt(self) -> str:
        return _REASONING_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {
            "question": "...",
            "evidence_chunks": [...],
            "graph_relations": [...],
            "web_results": [...]
        }
        Output payload: {"reasoned_answer": "...", "reasoning_steps": [...]}
        """
        question = message.payload.get("question", message.content)
        evidence_chunks = message.payload.get("evidence_chunks", [])
        graph_relations = message.payload.get("graph_relations", [])
        web_results = message.payload.get("web_results", [])

        prompt = self._build_reasoning_prompt(
            question, evidence_chunks, graph_relations, web_results
        )

        response = self.call_llm(prompt, temperature=0.2)
        logger.info(f"Reasoning agent produced {len(response)} chars of output")

        return self.create_message(
            content="Reasoning complete",
            receiver=AgentRole.FACT_CHECKER,
            payload={
                "reasoned_answer": response,
                "question": question,
                "evidence_used": len(evidence_chunks),
            },
        )

    def _build_reasoning_prompt(
        self,
        question: str,
        evidence_chunks: list[dict],
        graph_relations: list[dict],
        web_results: list[dict],
    ) -> str:
        parts = [f"# Research Question\n{question}\n"]

        # Vector evidence
        if evidence_chunks:
            parts.append("# Vector Retrieval Evidence")
            for i, chunk in enumerate(evidence_chunks[:15], 1):
                source = chunk.get("source", "unknown")
                content = chunk.get("content", "")[:500]
                parts.append(f"[V{i}] Source: {source}\n{content}\n")

        # Graph relationships
        if graph_relations:
            parts.append("# Knowledge Graph Relationships")
            for rel in graph_relations[:15]:
                parts.append(
                    f"  {rel.get('source_entity', '?')} "
                    f"--{rel.get('relationship', '?')}--> "
                    f"{rel.get('target_entity', '?')}"
                )

        # Web results
        if web_results:
            parts.append("# Web Search Results")
            for i, wr in enumerate(web_results[:10], 1):
                parts.append(
                    f"[W{i}] {wr.get('title', '')}\n"
                    f"    URL: {wr.get('url', '')}\n"
                    f"    {wr.get('snippet', '')[:300]}\n"
                )

        parts.append(
            "\nBased ONLY on the evidence above, provide a well-structured, "
            "evidence-grounded answer to the research question. "
            "Cite sources using [V1], [V2], [W1] etc. notation. "
            "If evidence is insufficient, state that clearly."
        )

        return "\n".join(parts)
