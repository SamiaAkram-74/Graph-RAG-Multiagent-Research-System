# GraphRAG-MARS: Graph RAG + Multi-Agent Research System

An advanced AI research assistant that combines **Knowledge Graphs**, **Vector RAG**, **Multi-Agent Reasoning**, and **Fact Verification** to produce evidence-grounded research reports.

## Architecture

```
User Question
      ↓
  Planner Agent         ← Decomposes into sub-questions
      ↓
  ┌─────────┬──────────┬──────────┐
  ↓         ↓          ↓          ↓
Vector    Graph     Web       ← Parallel retrieval
RAG       RAG      Search
  └─────────┴──────────┴──────────┘
      ↓
Reasoning Agent        ← Synthesises evidence
      ↓
Fact Checker           ← Verifies claims, flags hallucinations
      ↓
Report Generator       ← Structured research report
```

## 5 Experiment Configurations

| # | Configuration | Pipeline |
|---|---|---|
| 1 | **Baseline LLM** | Question → LLM → Answer |
| 2 | **Vector RAG** | Question → Vector Search → LLM → Answer |
| 3 | **Graph RAG** | Question → Knowledge Graph → LLM → Answer |
| 4 | **Hybrid RAG** | Question → Vector + Graph → LLM → Answer |
| 5 | **Multi-Agent** | Full pipeline with planning, reasoning, fact-checking |

## Quick Start

### 1. Setup

```bash
# Clone and install
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start with Docker

```bash
# Starts Neo4j + Backend API + Frontend
docker-compose up
```

- **API**: http://localhost:8080
- **Frontend**: http://localhost:8501
- **Neo4j Browser**: http://localhost:7474

### 3. Run Locally (without Docker)

```bash
# Start the API server
python main.py serve

# Ingest documents into vector store
python main.py ingest ./data/documents

# Build knowledge graph from documents
python main.py graph ./data/documents

# Run evaluation benchmarks
python main.py evaluate
```

### 4. Run the Frontend

```bash
streamlit run frontend/app.py
```

## Project Structure

```
├── main.py                     # CLI entry point
├── src/
│   ├── config.py               # Global configuration
│   ├── core/
│   │   ├── schemas.py          # Pydantic data models
│   │   ├── llm.py              # LLM abstraction (Gemini/OpenAI)
│   │   ├── base_agent.py       # Abstract agent base class
│   │   └── registry.py         # Agent registry
│   ├── agents/
│   │   ├── planner_agent.py    # Query decomposition
│   │   ├── vector_agent.py     # Vector DB retrieval
│   │   ├── graph_agent.py      # Knowledge graph retrieval
│   │   ├── web_agent.py        # Web search
│   │   ├── reasoning_agent.py  # Evidence synthesis
│   │   ├── fact_checker_agent.py # Claim verification
│   │   └── report_agent.py     # Report generation
│   ├── rag/
│   │   ├── documents.py        # Document loading (PDF/DOCX/TXT)
│   │   ├── chunking.py         # Text chunking
│   │   ├── embeddings.py       # Sentence embeddings
│   │   ├── vector_store.py     # ChromaDB/FAISS store
│   │   └── pipeline.py         # Full RAG pipeline
│   ├── graph/
│   │   ├── entity_extractor.py # LLM entity extraction
│   │   ├── graph_store.py      # Neo4j/NetworkX graph
│   │   └── retriever.py        # Graph query interface
│   ├── api/
│   │   ├── app.py              # FastAPI application
│   │   └── routes.py           # REST API endpoints
│   └── evaluation/
│       └── metrics.py          # Metrics + benchmark runner
├── frontend/
│   └── app.py                  # Streamlit web UI
├── data/
│   ├── documents/              # Upload research papers here
│   └── benchmarks/             # Evaluation datasets
├── tests/                      # Test suite
├── docker/                     # Docker configs
├── Dockerfile                  # Backend container
├── Dockerfile.frontend         # Frontend container
├── docker-compose.yml          # Full stack orchestration
└── requirements.txt            # Python dependencies
```

## Research Hypothesis

> **H1**: A hybrid Graph RAG + Vector RAG + Multi-Agent architecture produces more accurate and factually grounded answers to complex multi-hop research questions than conventional Vector RAG.

## Evaluation Metrics

| Category | Metrics |
|---|---|
| Retrieval | Precision@K, Recall@K, MRR, Context Relevance |
| Answer Quality | Factual Correctness, Faithfulness, Relevance, Completeness |
| Hallucination | Unsupported Claims / Total Claims |
| Agent Performance | Task Success Rate, Tool Calls, Self-Correction Rate |
| System Performance | Latency, Token Usage, API Cost |

## Technology Stack

- **Backend**: Python, FastAPI
- **LLM**: Google Gemini / OpenAI GPT-4
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2)
- **Vector DB**: ChromaDB / FAISS
- **Knowledge Graph**: Neo4j / NetworkX
- **Document Processing**: PyMuPDF, Unstructured
- **Frontend**: Streamlit
- **Deployment**: Docker, docker-compose

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/status` | System status |
| POST | `/api/documents/ingest` | Upload & ingest document |
| POST | `/api/documents/ingest-directory` | Ingest directory |
| POST | `/api/graph/build` | Build knowledge graph |
| GET | `/api/graph/summary` | Graph summary |
| POST | `/api/query` | Run research query |
| POST | `/api/evaluate/run` | Run benchmarks |

## License

MIT
