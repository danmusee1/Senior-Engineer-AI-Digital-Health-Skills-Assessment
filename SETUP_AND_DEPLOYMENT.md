# Setup & Deployment Guide

This document covers local development setup and a production deployment
plan for the Last Mile Health RAG system (backend, frontend, chainlit app,
and Postgres/pgvector).

## 1. Local Setup

### Prerequisites

- Docker and Docker Compose
- [Ollama](https://ollama.com) installed and running on the host machine
  (not in a container) with the following models pulled:

```bash
ollama pull llama3.2:latest
ollama pull nomic-embed-text
```

- Ollama must be reachable from containers. By default it binds to
  `127.0.0.1`, which containers cannot reach. Start it bound to all
  interfaces:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

On Linux, if running as a systemd service, set this in the service's
environment and restart it (`systemctl restart ollama`).

### Clone and configure

```bash
git clone <repo-url>
cd Senior-Engineer-AI-Digital-Health-Skills-Assessment
cp .env.example .env
```

Edit `.env` and confirm the following, in particular:

```env
DATABASE_URL=postgresql://postgres:postgres@relational_db:5432/postgres
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIM=768
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
API_KEY=
RATE_LIMIT_ENABLED=true
```

**Platform-specific note on `OLLAMA_BASE_URL`:**

| Platform | Value |
|---|---|
| Docker Desktop (Windows/Mac) | `http://host.docker.internal:11434` |
| Linux (with `extra_hosts` mapping `host.docker.internal:host-gateway`, already configured in `docker-compose.yaml`) | `http://host.docker.internal:11434` |
| Linux fallback (if the above doesn't resolve) | `http://172.17.0.1:11434` (confirm with `docker network inspect bridge \| grep Gateway`) |

### Start the stack

```bash
docker compose -p assessment up -d --build
```

This starts four services:

- `relational_db` — Postgres 16 with the `pgvector` extension
- `backend` — FastAPI RAG API on port `6100`
- `frontend` — Next.js UI on port `3000`
- `chainlit` — Chainlit chat app on port `8000`

### Verify

```bash
# Backend health (checks DB and Ollama connectivity)
curl http://localhost:6100/health

# Frontend
open http://localhost:3000

# Logs
docker compose -p assessment logs -f backend
```

A healthy response from `/health` looks like:

```json
{"status": "ok", "database": true, "ollama": true}
```

If `ollama: false`, re-check the `OLLAMA_BASE_URL` value and that Ollama is
bound to `0.0.0.0`, then:

```bash
docker compose -p assessment up -d --force-recreate backend
```

### Using the app

1. Go to `http://localhost:3000/upload`, upload a PDF (max 20MB).
2. Ingestion runs in the background — the document list shows status
   (`pending` → `processing` → `completed`/`failed`) and polls
   automatically until done.
3. Go to `http://localhost:3000/chat` and ask questions. Answers are
   grounded in the most relevant chunks from completed documents, with
   sources shown below each answer.

### Running tests

Tests require their own Postgres database (`lmh_rag_test` by default) on
the same Postgres server:

```bash
docker compose -p assessment up -d relational_db
cd backend
pip install -r requirements.txt --break-system-packages
pytest
```

No real Ollama calls are made in tests — embeddings and generation are
mocked (see `conftest.py`).

### Common local issues

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError` on startup | Stale/old source file not matching current module layout | Confirm file content matches latest version; rebuild with `--build` |
| `Cannot assign requested address` calling Ollama | `OLLAMA_BASE_URL=http://localhost:11434` inside a container | Use `host.docker.internal` (see table above) and ensure Ollama binds `0.0.0.0` |
| `invalid input value for enum document_status` | Stale Postgres enum from an earlier schema version | `docker compose -p assessment down -v` to recreate the DB from scratch (dev only — destroys data) |
| `service "backend" is not running` on `exec` | Missing `-p assessment` project flag, or container actually crashed | Re-run with `-p assessment`; check `docker compose -p assessment ps` |
| Upload succeeds but document stuck on `processing` | Background ingestion failed (check `error_message` on the document, and backend logs) | `docker compose -p assessment logs backend` |

---

## 2. Production Deployment Plan

This section describes how the current architecture extends to a real
production deployment, and which trade-offs from `ARCHITECTURE.md` should
be revisited first.

### 2.1 Target architecture

```
                         ┌────────────────────┐
 Users ──── HTTPS ──────▶│  Reverse proxy /    │
                         │  Load balancer      │
                         │  (e.g. ALB / Nginx) │
                         └─────────┬───────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                  ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │  Frontend     │  │  Backend API  │  │  Chainlit     │
          │  (Next.js)    │  │  (FastAPI,    │  │  (chat app)   │
          │  N replicas   │  │  N replicas)  │  │  N replicas   │
          └──────────────┘  └──────┬────────┘  └──────┬────────┘
                                    │                  │
                       ┌────────────┼──────────────────┘
                       ▼            ▼
              ┌─────────────┐  ┌──────────────┐
              │  Postgres + │  │  Ollama       │
              │  pgvector   │  │  (GPU host or │
              │  (managed)  │  │  managed LLM  │
              └─────────────┘  │  endpoint)    │
                                └──────────────┘
                       ▲
                       │
              ┌─────────────┐
              │  Redis       │  (rate limiting,
              │  (managed)   │   task queue broker)
              └─────────────┘
              ┌─────────────┐
              │  Task queue  │  (ingestion workers,
              │  workers     │   decoupled from API)
              └─────────────┘
```

### 2.2 Container images & registry

- Build production images via the existing Dockerfiles, tagged by git SHA
  and pushed to a container registry (ECR, GHCR, or equivalent).
- CI builds on merge to `main`; deployment pulls a specific tag, never
  `latest`, for reproducibility and easy rollback.

### 2.3 Configuration & secrets

- All values currently in `.env` move to the deployment platform's secret
  manager (AWS Secrets Manager, environment variables in ECS/Kubernetes,
  etc.) — never committed.
- `API_KEY` **must** be set to a strong random secret in any non-local
  environment (the app runs with auth disabled if unset — by design for
  local dev, but unacceptable in production).
- `ALLOWED_ORIGINS` set to the production frontend's actual domain(s),
  never `*`.
- `ENVIRONMENT=production`, `LOG_LEVEL=INFO` (or `WARNING` if log volume is
  a concern).

### 2.4 Database

- Use a managed Postgres instance with the `pgvector` extension available
  (AWS RDS for Postgres supports pgvector; or a managed pgvector-compatible
  service).
- Run schema setup via **Alembic migrations** rather than
  `Base.metadata.create_all()` — this is the single highest-priority change
  before production, since `create_all()` cannot evolve an existing schema
  (as already encountered during development when `documents` gained new
  columns).
- Enable automated backups and point-in-time recovery on the managed
  instance.
- Size the connection pool (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) based on
  `gunicorn` worker count × expected replica count, staying under the
  database's max connection limit.

### 2.5 Ollama / LLM serving

The current setup assumes Ollama running on the same host as Docker, which
does not extend to a multi-instance production deployment. Options, in
order of effort:

1. **Dedicated Ollama host(s)**: run Ollama on a GPU-equipped VM/instance,
   with `OLLAMA_BASE_URL` pointing at its private network address. Simplest
   migration from the current setup — only the URL changes.
2. **Managed inference endpoint**: replace Ollama calls with a managed LLM
   provider's API (e.g. Bedrock, an OpenAI-compatible endpoint, or a
   self-hosted vLLM/TGI server) for better scaling and uptime guarantees.
   `service.py`'s `_post_with_retry` / `get_embedding` / `generate_response`
   are the only functions that would need to change — the rest of the
   pipeline is provider-agnostic.
3. Whichever option, ensure the embedding model and `OLLAMA_EMBEDDING_DIM`
   stay consistent — changing embedding models requires re-ingesting all
   documents, since the `pgvector` column dimension is fixed at table
   creation.

### 2.6 Ingestion: move off in-process `BackgroundTasks`

As noted in `ARCHITECTURE.md`, `BackgroundTasks` runs ingestion in the same
worker/process handling API requests. For production:

- Introduce a task queue (Celery, arq, or a simple Postgres-backed job
  table polled by a worker) with Redis or the database as the broker.
- `process_document(document_id, file_bytes)` is already queue-friendly
  (plain data in, no return value, own DB session) — wrap it as a queue
  task without changing its internals.
- Run ingestion workers as a separate deployment/service, scaled
  independently from the API (ingestion is CPU/embedding-bound; API
  serving is I/O-bound).
- Store uploaded file bytes in object storage (S3 or equivalent) rather
  than passing them in-memory to the task, so workers in a different
  process/host can retrieve them.

### 2.7 Rate limiting at scale

The current `RateLimitMiddleware` is in-process and per-worker — with
multiple gunicorn workers or replicas, the effective limit is
`configured_limit × workers × replicas`. For production:

- Replace the in-memory `_hits` dict with Redis (`INCR` + `EXPIRE` per
  client IP per window), keeping the same `dispatch()` interface.
- Consider rate limiting at the load balancer / API gateway layer as a
  first line of defense (e.g. AWS WAF rate-based rules) in addition to
  application-level limiting.

### 2.8 Logging & observability

- Swap the logging formatter from plain text to JSON
  (`python-json-logger`) for ingestion into a log aggregation platform
  (CloudWatch Logs Insights, Grafana Loki, Datadog, etc.) — isolated change
  to `app/core/logging_config.py` only.
- Every error response includes `request_id`; ensure the chosen log
  platform supports searching by this field for incident correlation.
- Add application metrics (request latency, ingestion success/failure
  rates, Ollama call latency and error rates, queue depth) — Prometheus
  `/metrics` endpoint via `prometheus-fastapi-instrumentator` is a
  low-effort addition.
- Configure alerts on: `/health` returning `degraded`, ingestion failure
  rate exceeding a threshold, and elevated 5xx rate.

### 2.9 Networking & TLS

- TLS terminates at the load balancer / reverse proxy; internal
  service-to-service traffic (backend ↔ Postgres ↔ Ollama) stays within a
  private network/VPC.
- `RequestIDMiddleware` already supports an inbound `X-Request-ID` from an
  upstream load balancer — confirm the LB is configured to set this header
  for end-to-end correlation.

### 2.10 Authentication for production

The shared `API_KEY` model (documented as a deliberate trade-off for this
assessment's scope) should be replaced before handling real user data:

- Introduce per-user authentication (JWT issued after login against an
  identity provider), applied via a `Depends`-based dependency with the
  same shape as `require_api_key` — route signatures don't need to change.
- If the frontend currently sends any secret directly from the browser
  (e.g. via `NEXT_PUBLIC_API_KEY`), move those calls to server-side Next.js
  API routes so secrets never reach the client bundle.

### 2.11 Rollout strategy

- Deploy via rolling updates (ECS/Kubernetes) with health checks against
  `/health` gating traffic shift to new instances.
- Run Alembic migrations as a pre-deploy step (separate job/task), not on
  application startup, so multiple replicas don't race to apply migrations
  concurrently.
- Keep `down -v`-style destructive resets strictly to local/dev — never
  run against a production database volume.

### 2.12 Priority order for productionizing

If implementing incrementally, this is the recommended order based on risk
and blast radius:

1. Alembic migrations (schema changes currently destructive in practice)
2. Set `API_KEY`, restrict `ALLOWED_ORIGINS`, move secrets to a secret
   manager
3. Move Ollama to a stable, network-reachable host (or managed endpoint)
4. JSON logging + basic metrics/alerting
5. Task queue for ingestion (decouple from API workers)
6. Redis-backed rate limiting
7. Per-user authentication
