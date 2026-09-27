"""
Web Research Agent — searches the web for current information and
returns structured results with sources and URLs.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import AgentRole, AgentMessage, EvidenceChunk, WebResult


_WEB_SYSTEM_PROMPT = """\
You are the Web Research Agent in a multi-agent research system.
Your job is to formulate effective web search queries from a research
question and to evaluate the relevance of web search results.

Given a research question, provide:
1. Optimised search queries (2-4 different queries).
2. Key terms that must appear in relevant results.

Return JSON:
{
  "search_queries": ["query1", "query2"],
  "key_terms": ["term1", "term2"]
}
"""


class WebResearchAgent(BaseAgent):
    """Searches the web and returns structured evidence."""

    def __init__(self, llm=None):
        super().__init__(role=AgentRole.WEB_RESEARCH, llm=llm)

    def get_system_prompt(self) -> str:
        return _WEB_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {"query": "...", "max_results": 5}
        Output payload: {
            "evidence_chunks": [...],
            "web_results": [WebResult.model_dump(), ...]
        }
        """
        query = message.payload.get("query", message.content)
        max_results = message.payload.get("max_results", 5)

        # Generate search queries
        search_info = self._generate_queries(query)
        search_queries = search_info.get("search_queries", [query])

        # Execute web searches
        web_results: list[WebResult] = []
        evidence_chunks: list[EvidenceChunk] = []

        for sq in search_queries[:3]:
            results = self._search_web(sq, max_results // len(search_queries) + 1)
            web_results.extend(results)

        # Convert to evidence chunks
        for i, wr in enumerate(web_results[:max_results]):
            evidence_chunks.append(EvidenceChunk(
                chunk_id=f"web_{i:03d}",
                content=f"{wr.title}\n{wr.snippet}",
                source=wr.url,
                relevance_score=wr.relevance_score,
                metadata={"title": wr.title, "url": wr.url},
                retrieval_method="web",
            ))

        logger.info(f"Web research: {len(web_results)} results for '{query[:60]}...'")

        return self.create_message(
            content=f"Found {len(web_results)} web results",
            payload={
                "evidence_chunks": [c.model_dump() for c in evidence_chunks],
                "web_results": [r.model_dump() for r in web_results],
            },
        )

    def _generate_queries(self, query: str) -> dict[str, Any]:
        """Use LLM to generate optimised search queries."""
        prompt = f"Research question: {query}\nGenerate optimised web search queries."
        try:
            raw = self.call_llm(prompt, temperature=0.1)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return {"search_queries": [query], "key_terms": []}

    def _search_web(self, query: str, num_results: int = 5) -> list[WebResult]:
        """Execute a web search using DuckDuckGo."""
        results: list[WebResult] = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=num_results))
                for r in search_results:
                    results.append(WebResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source="duckduckgo",
                        relevance_score=0.7,
                    ))
        except ImportError:
            logger.warning("duckduckgo-search not installed — skipping web search")
        except Exception as e:
            logger.error(f"Web search failed: {e}")

        return results
