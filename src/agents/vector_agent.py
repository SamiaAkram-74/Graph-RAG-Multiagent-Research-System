"""
Vector Retrieval Agent — retrieves semantically relevant document chunks
from the vector database.
"""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import AgentRole, AgentMessage, EvidenceChunk


_VECTOR_SYSTEM_PROMPT = """\
You are the Vector Retrieval Agent in a multi-agent research system.
Your job is to analyse a search query and determine the best search terms
and strategy to retrieve relevant document chunks from a vector database.

Given a query, provide:
1. The key search phrases to use (as a JSON array).
2. Any query reformulations that might help retrieval.

Return JSON:
{
  "search_phrases": ["phrase1", "phrase2"],
  "reformulated_query": "..."
}
"""


class VectorRetrievalAgent(BaseAgent):
    """Retrieves evidence from the vector store."""

    def __init__(self, vector_store=None, llm=None):
        super().__init__(role=AgentRole.VECTOR_RETRIEVAL, llm=llm)
        self.vector_store = vector_store  # injected at runtime

    def get_system_prompt(self) -> str:
        return _VECTOR_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {"query": "...", "max_results": 10}
        Output payload: {"evidence_chunks": [EvidenceChunk.model_dump(), ...]}
        """
        query = message.payload.get("query", message.content)
        max_results = message.payload.get("max_results", 10)

        # Get search phrases from LLM
        search_info = self._get_search_strategy(query)
        search_phrases = search_info.get("search_phrases", [query])
        reformulated = search_info.get("reformulated_query", query)

        # Retrieve from vector store
        chunks: list[EvidenceChunk] = []
        if self.vector_store:
            raw_chunks = self.vector_store.search(
                query=reformulated,
                n_results=max_results,
            )
            for i, chunk in enumerate(raw_chunks):
                chunks.append(EvidenceChunk(
                    chunk_id=str(uuid.uuid4())[:8],
                    content=chunk.get("content", ""),
                    source=chunk.get("source", "unknown"),
                    relevance_score=chunk.get("score", 0.0),
                    metadata=chunk.get("metadata", {}),
                    retrieval_method="vector",
                ))
        else:
            logger.warning("No vector store configured — returning empty results")

        logger.info(f"Vector retrieval: {len(chunks)} chunks for query '{query[:60]}...'")

        return self.create_message(
            content=f"Retrieved {len(chunks)} chunks via vector search",
            payload={"evidence_chunks": [c.model_dump() for c in chunks]},
        )

    def _get_search_strategy(self, query: str) -> dict[str, Any]:
        """Use LLM to generate optimised search phrases."""
        import json
        prompt = f"Query: {query}\nGenerate search phrases for vector retrieval."
        try:
            raw = self.call_llm(prompt, temperature=0.0)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return {"search_phrases": [query], "reformulated_query": query}
