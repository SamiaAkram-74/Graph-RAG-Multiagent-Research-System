---
kind: business_term
name: Business Glossary
category: business_term
scope:
    - '**'
---

### GraphRAG-MARS
- Definition：The project's internal product name — a Graph RAG + Multi-Agent Research System that combines knowledge graphs, vector retrieval, multi-agent reasoning, and fact verification to produce evidence-grounded research reports.
- Aliases：GraphRAG MARS、GraphRAG+Multi-Agent Research System

### Planner Agent
- Definition：The first agent in the pipeline that decomposes a user's research question into sub-questions or sub-tasks before dispatching them to parallel retrieval agents.
- Aliases：planner

### Vector RAG
- Definition：Retrieval-augmented generation mode that answers questions by performing semantic search over a vector store of document chunks and feeding the top-k results to an LLM.
- Aliases：vector retrieval

### Graph RAG
- Definition：Retrieval-augmented generation mode that answers questions by querying a knowledge graph (Neo4j or NetworkX) for entity/relationship context around relevant entities.
- Aliases：graph retrieval

### Hybrid RAG
- Definition：Experiment configuration #4 that runs both vector and graph retrieval in parallel and feeds their combined results to the LLM.

### Multi-Agent
- Definition：Experiment configuration #5 — the full pipeline where a Planner Agent decomposes the question, multiple specialized agents retrieve in parallel, a Reasoning Agent synthesizes evidence, a Fact Checker verifies claims, and a Report Generator produces the final structured report.

### Evidence Chunk
- Definition：A normalized unit of retrieved information (from vector search, graph traversal, or web search) containing content, source, relevance score, and metadata, consumed downstream by the Reasoning and Fact Checker agents.
- Aliases：chunk

### Fact Checker
- Definition：Agent that inspects claims produced by the Reasoning Agent against the gathered evidence and flags unsupported or hallucinated statements.
- Aliases：fact-checker

### Report Generator
- Definition：Final agent in the pipeline that converts synthesized evidence into a structured research report.
- Aliases：report agent

### Baseline LLM
- Definition：Experiment configuration #1 — a direct question-to-answer pass through the LLM with no retrieval augmentation, used as the control baseline for evaluation.
