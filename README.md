# Cloud Incident Response Agent

An agentic AI system that investigates cloud-service incidents using live-style operational evidence, retrieved runbook guidance, structured diagnosis, deterministic validation, and human approval before remediation.

The project combines LangGraph, LangChain, Model Context Protocol (MCP), PostgreSQL with pgvector, sentence-transformer embeddings, cross-encoder reranking, FastAPI, Ollama, SQLAlchemy, Alembic, and automated evaluations.

> This is a local demonstration project. Remediation is simulated and does not modify real infrastructure.

## Key Features

- Multi-step incident investigation orchestrated with LangGraph
- MCP tools for metrics, logs, deployment history, runbook search, and simulated rollback
- Persistent runbook chunks and embeddings in PostgreSQL with pgvector
- HNSW vector index using cosine distance
- Cross-encoder reranking after semantic candidate retrieval
- Relevance filtering for unsupported questions
- Structured LLM output using Pydantic schemas
- Deterministic diagnosis validation and retry control
- Human-in-the-loop approval before production-style actions
- Persistent LangGraph checkpoints using SQLite
- FastAPI endpoints for starting and resuming investigations
- Structured request and workflow logging
- Retrieval, relevance, and end-to-end agent evaluations

## Architecture

```mermaid
flowchart TD
    A[Incident request] --> B[FastAPI]
    B --> C[LangGraph workflow]
    C --> D[MCP tools]
    D --> E[Metrics JSON]
    D --> F[Logs JSON]
    D --> G[Deployments JSON]
    D --> H[Runbook retrieval]
    H --> I[PostgreSQL and pgvector]
    I --> J[Cross-encoder reranking]
    J --> C
    C --> K[Ollama diagnosis]
    K --> L[Deterministic validation]
    L -->|Invalid and retry available| K
    L -->|Valid| M[Remediation proposal]
    M --> N[Human approval]
    N -->|Approved| O[Simulated execution]
    N -->|Rejected| P[No execution]
```

## Investigation Workflow

1. An incident description and service name enter the LangGraph workflow.
2. The agent calls MCP tools to collect metrics, logs, deployments, and runbook guidance.
3. Runbook search creates a query embedding and searches pgvector with cosine distance.
4. The cross-encoder reranks the semantic candidates.
5. Results below the configured relevance threshold are removed.
6. Ollama produces a structured diagnosis through LangChain.
7. Deterministic rules validate severity, supporting evidence, recommended action, and approval requirements.
8. An invalid diagnosis can be retried with validation feedback.
9. A valid diagnosis produces a remediation proposal.
10. LangGraph pauses for human approval.
11. Approved remediation calls a simulated rollback MCP tool. Rejected remediation finishes without execution.

## Data Storage

The project intentionally uses different storage systems for different workloads.

| Data | Storage | Purpose |
|---|---|---|
| Runbook metadata | PostgreSQL | Tracks source files and content hashes |
| Runbook chunks | PostgreSQL | Stores searchable runbook sections |
| Embeddings | pgvector | Supports semantic similarity search |
| Metrics | Local JSON fixtures | Simulates CloudWatch, Prometheus, or Datadog |
| Logs | Local JSON fixtures | Simulates CloudWatch Logs, OpenSearch, or Splunk |
| Deployments | Local JSON fixtures | Simulates CI/CD and Kubernetes deployment history |
| LangGraph checkpoints | SQLite | Persists workflow state and approval interruptions |
| Evaluation cases | JSON | Stores test questions and expected outcomes |

### pgvector Tables

`runbook_documents` stores one row for each Markdown runbook:

- Runbook name
- Filename and path
- File hash
- Creation and update timestamps

`runbook_chunks` stores the searchable sections:

- Parent document ID
- Chunk index
- Heading
- Content
- Content hash
- 384-dimensional embedding
- Creation and update timestamps

Runbook files are synchronized by content hash. New and changed files are embedded, unchanged files are skipped, and deleted files are removed from the database.

## Retrieval Pipeline

```text
Markdown runbooks
    -> heading-aware chunks
    -> normalized 384-dimensional embeddings
    -> PostgreSQL/pgvector

Incident query
    -> normalized query embedding
    -> pgvector cosine search
    -> candidate chunks
    -> cross-encoder reranking
    -> relevance threshold
    -> MCP result
    -> LangGraph diagnosis
```

The default models are:

```text
Embedding: sentence-transformers/all-MiniLM-L6-v2
Reranker:  cross-encoder/ms-marco-MiniLM-L6-v2
LLM:       llama3.2:3b through Ollama
```

The relevance threshold is currently calibrated to `-6.0` using supported and unsupported evaluation cases. Cross-encoder scores are model-specific, so this value should be recalibrated when the reranker model or corpus changes.

## MCP Tools

The MCP server exposes these tools:

| Tool | Purpose |
|---|---|
| `get_service_metrics` | Returns latency, error rate, resource use, and instance health |
| `search_application_logs` | Searches service logs by text and level |
| `get_recent_deployments` | Returns recent versions and configuration changes |
| `search_runbooks` | Runs pgvector retrieval, reranking, and relevance filtering |
| `simulate_rollback` | Simulates an approved rollback without changing real infrastructure |

The operational data implementations can later be replaced with CloudWatch, Datadog, OpenSearch, Splunk, Kubernetes, Argo CD, or GitHub Actions clients without changing the agent-facing MCP tool contracts.

## Project Structure

```text
cloud-incident-response-agent/
├── data/
│   ├── deployments/
│   ├── evaluations/
│   │   ├── baseline_v1.json
│   │   ├── incidents.json
│   │   ├── runbook_relevance_cases.json
│   │   └── runbook_retrieval_cases.json
│   ├── logs/
│   ├── metrics/
│   └── runbooks/
├── migrations/
├── scripts/
│   ├── run_evaluations.py
│   ├── run_investigation.py
│   ├── run_relevance_evaluations.py
│   ├── run_retrieval_evaluations.py
│   ├── sync_runbooks.py
│   └── test_mcp_client.py
├── src/cloud_incident_response_agent/
│   ├── agents/
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   └── state.py
│   ├── api/
│   │   └── incidents.py
│   ├── mcp_server/
│   │   └── server.py
│   ├── models/
│   │   └── runbook.py
│   ├── retrieval/
│   │   ├── runbook_loader.py
│   │   ├── runbook_search.py
│   │   └── schemas.py
│   ├── schemas/
│   │   ├── diagnosis.py
│   │   └── remediation.py
│   ├── services/
│   │   ├── embeddings.py
│   │   ├── operational_data.py
│   │   ├── remediation.py
│   │   └── runbook_sync.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   └── observability.py
├── tests/
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
└── README.md
```

## Prerequisites

- Python 3.11
- `uv`
- Docker Desktop
- Ollama
- Git
- Node.js and npm only if you want to use the graphical MCP Inspector

## Local Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/cloud-incident-response-agent.git
cd cloud-incident-response-agent
uv sync
```

### 2. Create `.env`

Create `.env` in the project root:

```env
APP_NAME=Cloud Incident Response Agent
APP_ENVIRONMENT=development

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

MCP_SERVER_URL=http://127.0.0.1:8001/mcp

DATABASE_URL=postgresql+psycopg://incident_user:incident_password@localhost:5434/incident_agent

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L6-v2

RETRIEVAL_CANDIDATE_COUNT=30
RETRIEVAL_TOP_K=5
MINIMUM_RERANKER_SCORE=-6.0
```

Do not commit `.env`.

### 3. Start PostgreSQL with pgvector

```bash
docker compose up -d
docker compose ps
```

The local database is exposed on port `5434` to avoid conflicting with a PostgreSQL instance on port `5432`.

### 4. Apply database migrations

For a new database:

```bash
uv run alembic upgrade head
```

Check the active revision:

```bash
uv run alembic current
```

`alembic stamp head` is only for an existing database whose tables were created before Alembic was introduced. Do not use it for a new empty database.

### 5. Synchronize runbooks

```bash
uv run python scripts/sync_runbooks.py
```

The first run creates embeddings. Later runs skip unchanged files.

### 6. Start Ollama

```bash
ollama serve
```

In another terminal:

```bash
ollama pull llama3.2:3b
ollama list
```

Verify Ollama:

```bash
curl http://127.0.0.1:11434/api/tags
```

### 7. Start the MCP server

```bash
uv run mcp run \
src/cloud_incident_response_agent/mcp_server/server.py \
--transport streamable-http
```

Use the endpoint printed by the MCP command. Set `MCP_SERVER_URL` in `.env` to that endpoint if its host or port differs from the example.

Test the tools from another terminal:

```bash
uv run python scripts/test_mcp_client.py
```

### 8. Start FastAPI

Use a port different from the MCP server:

```bash
uv run uvicorn \
cloud_incident_response_agent.main:app \
--reload \
--port 8002
```

Open:

```text
http://127.0.0.1:8002/docs
```

Health check:

```bash
curl http://127.0.0.1:8002/health
```

## Run an Investigation

With PostgreSQL, Ollama, and the MCP server running:

```bash
uv run python scripts/run_investigation.py
```

The script:

1. Starts an investigation with a unique LangGraph thread ID.
2. Collects evidence through MCP.
3. Generates and validates the diagnosis.
4. Builds a rollback proposal when appropriate.
5. Pauses for reviewer approval.
6. Resumes the same workflow thread.
7. Simulates execution only when approved.

## Human Approval

The workflow uses LangGraph `interrupt()` and `Command` to pause and resume execution.

Approval data includes:

- Reviewer name
- Approval or rejection
- Optional comment
- Proposed action
- Current and target versions
- Risk level
- Diagnosis and supporting evidence

No rollback occurs without explicit approval. The current rollback tool is simulated and reports `changes_applied: false`.

## Evaluation

### Unit tests

```bash
uv run pytest -v
```

### Positive retrieval evaluation

Measures pgvector candidate quality and cross-encoder ranking:

```bash
uv run python scripts/run_retrieval_evaluations.py
```

Metrics include:

- Recall@5
- Mean Reciprocal Rank
- Top-1 accuracy
- Semantic and reranked positions
- Retrieval latency
- Reranking latency

### Relevance and rejection evaluation

Tests both supported and unsupported queries through the complete `search_runbooks()` function:

```bash
uv run python scripts/run_relevance_evaluations.py
```

Metrics include:

- Relevant-query retrieval accuracy
- Unsupported-query rejection accuracy
- Overall accuracy
- Average latency

### End-to-end agent evaluation

Tests diagnosis quality, evidence coverage, severity, approval behavior, validation, and latency:

```bash
uv run python scripts/run_evaluations.py
```

## Latest Local Evaluation Results

| Evaluation | Result |
|---|---:|
| Positive retrieval cases | 10/10 passed |
| Semantic Recall@5 | 1.00 |
| Semantic MRR | 1.00 |
| Semantic Top-1 accuracy | 1.00 |
| Reranked Recall@5 | 1.00 |
| Reranked MRR | 1.00 |
| Reranked Top-1 accuracy | 1.00 |
| Relevance cases | 10/10 passed |
| Relevant-query accuracy | 1.00 |
| Unsupported-query rejection accuracy | 1.00 |
| Previously validated agent cases | 6/6 passed |

The first request is slower because the embedding and reranker models load into memory. Warm requests are significantly faster.

## Database Inspection

List documents:

```bash
docker compose exec database \
psql -U incident_user -d incident_agent \
-c "SELECT id, runbook_name, file_name FROM runbook_documents ORDER BY id;"
```

List chunks:

```bash
docker compose exec database \
psql -U incident_user -d incident_agent \
-c "SELECT document_id, chunk_index, heading, LEFT(content, 80) FROM runbook_chunks ORDER BY document_id, chunk_index;"
```

Verify vector dimensions:

```bash
docker compose exec database \
psql -U incident_user -d incident_agent \
-c "SELECT id, heading, vector_dims(embedding) AS dimensions FROM runbook_chunks ORDER BY id;"
```

Verify indexes:

```bash
docker compose exec database \
psql -U incident_user -d incident_agent \
-c "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'runbook_chunks';"
```

PostgreSQL may choose a sequential scan for a tiny corpus. That is expected. The HNSW index becomes useful as the number of chunks grows.

## Safety and Reliability Controls

- Structured MCP tool parameters
- Service-name validation
- Pydantic diagnosis and remediation schemas
- Deterministic evidence validation
- Maximum diagnosis attempts
- Relevance filtering for retrieved runbooks
- Human approval for rollback, restart, scaling, and configuration changes
- Persistent workflow checkpoints
- Simulated remediation only
- Request IDs and structured logs
- Database migrations with Alembic

## Development Notes

- pgvector stores runbook knowledge, not evaluation cases.
- Metrics, logs, and deployments are local fixtures that represent external operational systems.
- SQLite and PostgreSQL are both intentional: SQLite stores LangGraph checkpoints, while PostgreSQL stores vector-search data.
- Cross-encoder scores are not probabilities. Recalibrate the threshold when changing the model or corpus.
- Generated evaluation results and checkpoint databases should normally be excluded from Git.

## Current Limitations

- Operational data comes from local JSON instead of real cloud systems.
- Ollama runs locally and is not configured for horizontal scaling.
- The retrieval corpus is small, so PostgreSQL may prefer a sequential scan over HNSW.
- Authentication and authorization are not yet implemented for FastAPI or MCP.
- The rollback tool is simulated.
- The relevance threshold is calibrated on a small evaluation dataset.

## Future Improvements

- Replace JSON operational data with CloudWatch, OpenSearch, Kubernetes, and CI/CD integrations
- Add API authentication, authorization, rate limiting, and audit retention
- Move LangGraph checkpoints to a durable PostgreSQL checkpointer
- Add tracing with OpenTelemetry or LangSmith
- Add hybrid keyword and vector retrieval
- Expand the runbook corpus and adversarial evaluation set
- Add model and threshold versioning
- Add Docker images for the FastAPI and MCP services
- Deploy PostgreSQL to a managed provider and the services to a cloud runtime
- Add CI checks for unit tests, migrations, linting, and retrieval regressions