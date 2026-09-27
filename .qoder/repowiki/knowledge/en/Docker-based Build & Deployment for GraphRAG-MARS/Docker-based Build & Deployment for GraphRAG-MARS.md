---
kind: build_system
name: Docker-based Build & Deployment for GraphRAG-MARS
category: build_system
scope:
    - '**'
source_files:
    - Dockerfile
    - Dockerfile.frontend
    - docker-compose.yml
    - requirements.txt
    - main.py
    - .env.example
---

## Build System Overview

GraphRAG-MARS uses a **Python-pip + Docker** build and deployment strategy. There is no Makefile, no `setup.py`/`pyproject.toml`, no CI pipeline, and no cross-compilation toolchain — the project is built by installing Python dependencies via `pip` and packaging the application into container images with Docker.

### Core Artifacts

- **`requirements.txt`** — single source of truth for all Python dependencies (backend, frontend, evaluation, utilities). Dependencies are pinned with minimum version constraints (`>=`) rather than exact pins.
- **`Dockerfile`** — builds the backend image from `python:3.11-slim`. Installs system `build-essential`, then pip-installs `requirements.txt`, copies `src/` and `.env.example`, creates `data/documents`, `data/benchmarks`, `data/eval_results` directories, exposes port 8080, and runs `uvicorn src.api.app:app --host 0.0.0.0 --port 8080`.
- **`Dockerfile.frontend`** — builds the Streamlit frontend image from `python:3.11-slim`, installs a minimal set of packages (`streamlit`, `requests`, `pandas`, `plotly`), copies `frontend/app.py` and `src/config.py`, exposes port 8501, and runs `streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0`.
- **`docker-compose.yml`** — orchestrates three services:
  - `neo4j` (image `neo4j:5-community`, with APOC plugin, healthcheck via `neo4j status`, persistent volume `neo4j_data`).
  - `backend` (built from `Dockerfile`, depends on `neo4j` being healthy, mounts `./data:/app/data`, passes Neo4j and LLM env vars).
  - `frontend` (built from `Dockerfile.frontend`, depends on `backend`).

### Local Development Entry Point

- **`main.py`** is the CLI entry point using `argparse` subcommands: `serve`, `ingest <path>`, `graph <path>`, `evaluate`. It configures `loguru` logging and can be run directly with `python main.py serve` or invoked from inside containers.

### Configuration

- Environment variables are templated in **`.env.example`** and injected at runtime via `docker-compose.yml` (e.g. `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `LLM_PROVIDER`, `GEMINI_API_KEY`, `VECTOR_DB_TYPE`). The backend Dockerfile copies `.env.example` as `.env` so that `python-dotenv` can load defaults.

### Testing

- Tests live under `tests/test_core.py` and import `pytest`, but there is no `pytest.ini`, `tox.ini`, or CI step to discover/run them automatically. Running tests locally requires `pip install pytest` and invoking `pytest` manually.

### Notable Conventions & Constraints

- **Single-stage Docker images**: both images use `python:3.11-slim` as the base; no multi-stage caching optimization beyond copying `requirements.txt` before `src/` to leverage pip cache layers.
- **No package distribution**: there is no `setup.py`, `pyproject.toml`, wheel/sdist generation, or PyPI publishing target — the project is consumed only as source code or container images.
- **Dependency pinning policy**: `requirements.txt` uses `>=` lower bounds (e.g. `fastapi>=0.110.0`), not exact pins, which means reproducible builds rely on the Docker layer cache and pip's default resolution behavior.
- **Service ordering**: `docker-compose.yml` enforces startup order via `depends_on` with `condition: service_healthy` for Neo4j, ensuring the backend only starts after the graph database is ready.
- **Data persistence**: Neo4j data is persisted to a named Docker volume (`neo4j_data`); application data is bind-mounted from `./data` into the backend container.