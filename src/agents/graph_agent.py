"""
Graph Retrieval Agent — retrieves entity relationships and connected
concepts from the knowledge graph.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import AgentRole, AgentMessage, EvidenceChunk, GraphRelation


_GRAPH_SYSTEM_PROMPT = """\
You are the Graph Retrieval Agent in a multi-agent research system.
Your job is to identify the key entities and concepts in a query that
should be looked up in a knowledge graph.

Given a query, extract:
1. The main entities to search for.
2. The types of relationships to follow.
3. The maximum hop depth (1-3).

Return JSON:
{
  "entities": ["entity1", "entity2"],
  "relationship_types": ["causes", "affects"],
  "hop_depth": 2
}
"""


class GraphRetrievalAgent(BaseAgent):
    """Retrieves evidence from the knowledge graph."""

    def __init__(self, graph_store=None, llm=None):
        super().__init__(role=AgentRole.GRAPH_RETRIEVAL, llm=llm)
        self.graph_store = graph_store  # injected at runtime

    def get_system_prompt(self) -> str:
        return _GRAPH_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {"query": "...", "max_results": 10}
        Output payload: {
            "evidence_chunks": [...],
            "graph_relations": [GraphRelation.model_dump(), ...]
        }
        """
        query = message.payload.get("query", message.content)
        max_results = message.payload.get("max_results", 10)

        # Extract entities from the query using LLM
        entity_info = self._extract_entities(query)
        entities = entity_info.get("entities", [])
        hop_depth = entity_info.get("hop_depth", 2)
        rel_types = entity_info.get("relationship_types", [])

        # Query the knowledge graph
        relations: list[GraphRelation] = []
        evidence_chunks: list[EvidenceChunk] = []

        if self.graph_store:
            raw_relations = self.graph_store.query_entities(
                entities=entities,
                hop_depth=hop_depth,
                relationship_types=rel_types,
                limit=max_results,
            )
            for rel in raw_relations:
                relations.append(GraphRelation(
                    source_entity=rel.get("source", ""),
                    relationship=rel.get("relationship", ""),
                    target_entity=rel.get("target", ""),
                    source_document=rel.get("source_doc"),
                    weight=rel.get("weight", 1.0),
                ))

            # Also get textual evidence from graph node properties
            raw_chunks = self.graph_store.get_entity_context(
                entities=entities, limit=max_results
            )
            for chunk in raw_chunks:
                evidence_chunks.append(EvidenceChunk(
                    chunk_id=chunk.get("id", ""),
                    content=chunk.get("content", ""),
                    source=chunk.get("source", "knowledge_graph"),
                    relevance_score=chunk.get("score", 0.5),
                    retrieval_method="graph",
                ))
        else:
            logger.warning("No knowledge graph configured — returning empty results")

        logger.info(
            f"Graph retrieval: {len(relations)} relations, "
            f"{len(evidence_chunks)} context chunks for entities {entities}"
        )

        return self.create_message(
            content=f"Retrieved {len(relations)} relations from knowledge graph",
            payload={
                "evidence_chunks": [c.model_dump() for c in evidence_chunks],
                "graph_relations": [r.model_dump() for r in relations],
            },
        )

    def _extract_entities(self, query: str) -> dict[str, Any]:
        """Use LLM to extract entities and relationship types from the query."""
        prompt = f"Query: {query}\nExtract key entities and relationship types for graph search."
        try:
            raw = self.call_llm(prompt, temperature=0.0)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            # Fallback: use query words as entities
            words = query.split()[:5]
            return {"entities": words, "relationship_types": [], "hop_depth": 1}
