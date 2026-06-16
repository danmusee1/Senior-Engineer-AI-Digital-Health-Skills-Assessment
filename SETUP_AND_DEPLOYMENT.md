# Setup & Deployment Guide

This document covers local development setup and a production deployment
plan for the Last Mile Health RAG system (backend, frontend, Chainlit, and
Postgres/pgvector).

---

## 1. Local Setup

### 1.1 Prerequisites

- **Docker and Docker Compose** — [install Docker](https://docs.docker.com/get-docker/)
- **An LLM provider** — choose one:

  | | Option A — Groq | Option B — Ollama only |
  |---|---|---|
  | Speed | Fast (cloud inference) | Slow on CPU, fast on GPU |
  | Cost | Free (no credit card) | Free |
  | Privacy | Data leaves your machine | Fully local |
  | GPU required | No | No (but strongly recommended) |

> **Embeddings always run via Ollama** regardless of LLM provider choice.
> Groq has no embeddings endpoint, so Ollama is required in both cases —
> the difference is only where text *generation* happens.

---

### 1.2 Install Ollama and pull models

Install [Ollama](https://ollama.com) on the **host machine** (not in a container).

**Option A — Groq (embeddings only via Ollama):**

```bash
ollama pull nomic-embed-text
```

**Option B — Ollama only (generation + embeddings):**

```bash
ollama pull llama3.2:latest
ollama pull nomic-embed-text
```

Start Ollama bound to all interfaces so containers can reach it:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

> **Linux systemd**: add `Environment="OLLAMA_HOST=0.0.0.0"` to the Ollama
> service file and run `systemctl restart ollama`.

By default Ollama binds to `127.0.0.1` — containers cannot reach that
address. `OLLAMA_HOST=0.0.0.0` is required, not optional.

---

### 1.3 Get a Groq API key (Option A only)

1. Sign up at [console.groq.com](https://console.groq.com) — free, no credit card.
2. Go to **API Keys** and create a new key.
3. Copy it — you will paste it into `.env` in the next step.

> **Security**: never commit API keys to version control. `.env` is already
> in `.gitignore`. Never paste real keys into chat logs, issues, or docs.

---

### 1.4 Configure environment variables

```bash
git clone <repo-url>
cd Senior-Engineer-AI-Digital-Health-Skills-Assessment
cp .env.example .env
```

Open `.env` and configure based on your provider:

**Option A — Groq:**

```dotenv
# LLM — Groq (OpenAI-compatible)
LLM_PROVIDER=openai_compatible
LLM_API_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk_your_key_here
LLM_API_MODEL=llama-3.1-8b-instant

# Embeddings — Ollama (Groq has no embeddings endpoint)
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIM=768
```

**Option B — Ollama only:**

```dotenv
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIM=768
```

**`OLLAMA_BASE_URL` — platform-specific values:**

`localhost` inside a container refers to the container itself, not your host.

| Platform | `OLLAMA_BASE_URL` |
|---|---|
| Docker Desktop (Windows / Mac) | `http://host.docker.internal:11434` |
| Linux | `http://host.docker.internal:11434` — requires `extra_hosts` mapping already set in `docker-compose.yaml` |
| Linux fallback | `docker network inspect bridge \| grep Gateway` → use that IP, e.g. `http://172.17.0.1:11434` |

**Other variables to confirm:**

```dotenv
DATABASE_URL=postgresql://postgres:postgres@relational_db:5432/postgres
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:6100
API_KEY=
RATE_LIMIT_ENABLED=true
```

For the full annotated reference of every variable, see `ENVIRONMENT.md`.

---

### 1.5 Start the stack

```bash
docker compose -p assessment up -d --build
```

| Service | Purpose | Port |
|---|---|---|
| `relational_db` | Postgres 16 + pgvector | `5432` |
| `backend` | FastAPI RAG API | `6100` |
| `frontend` | Next.js UI | `3000` |
| `chainlit` | Chainlit chat interface | `8000` |

---

### 1.6 Verify

```bash
curl http://localhost:6100/health
docker compose -p assessment logs -f backend
```

**Expected — Groq:**
```json
{"status": "ok", "database": true, "llm": true, "llm_provider": "openai_compatible"}
```

**Expected — Ollama:**
```json
{"status": "ok", "database": true, "llm": true, "llm_provider": "ollama"}
```

If `"llm": false`, see the troubleshooting table below.

---

### 1.7 Using the app

1. Go to `http://localhost:3000/upload` and upload a PDF (max 20 MB).
2. Watch the status badge: `pending` → `processing` → `completed` / `failed`.
3. Once `completed`, go to `http://localhost:3000/chat` and ask questions.
4. Or use Chainlit at `http://localhost:8000` for a conversational experience.

---

### 1.8 Running tests

All external calls are mocked — no LLM provider or GPU required.

**Backend:**
```bash
docker compose -p assessment up -d relational_db
cd backend
pip install -r requirements.txt
pytest -v
```

**Frontend:**
```bash
cd frontend
npm install
npx jest
```

---

### 1.9 Stopping services

```bash
# Stop containers, keep data
docker compose -p assessment down

# Stop containers AND wipe database (destroys all uploaded documents)
docker compose -p assessment down -v
```

---

### 1.10 Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `"llm": false` (Groq) | Missing or invalid `LLM_API_KEY` | Paste a valid key from [console.groq.com](https://console.groq.com); `--force-recreate backend` |
| `"llm": false` (Ollama) | Ollama not reachable from container | Check `OLLAMA_BASE_URL` matches your platform; confirm `OLLAMA_HOST=0.0.0.0` |
| `Cannot assign requested address` | `localhost` used inside container | Change `OLLAMA_BASE_URL` to `http://host.docker.internal:11434` |
| `invalid input value for enum document_status` | Stale Postgres schema | `docker compose -p assessment down -v` then `up -d --build` (dev only — destroys data) |
| `service "backend" is not running` on `exec` | Missing `-p assessment` flag | Re-run with `docker compose -p assessment exec backend ...` |
| Document stuck on `processing` | Background ingestion failed | Check `GET /rag/documents/{id}` for `error_message`; check backend logs |
| Duplicate upload but document is `failed` | Previous attempt failed after record was created | `DELETE /rag/documents/{id}` then re-upload |
| Embeddings fail with Groq | `EMBEDDING_PROVIDER=openai_compatible` set without a valid endpoint | Set `EMBEDDING_PROVIDER=ollama` — Groq has no embeddings endpoint |

---

## 2. Production Deployment Plan

### 2.1 Target architecture

```
                         ┌────────────────────┐
 Users ──── HTTPS ──────▶│  Load balancer /    │
                         │  Reverse proxy      │
                         │  (ALB / Nginx)      │
                         └─────────┬───────────┘
                                   │
                  ┌────────────────┼────────────────┐
                  ▼                ▼                 ▼
          ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
          │  Frontend   │  │  Backend API │  │  Chainlit   │
          │  (Next.js)  │  │  (FastAPI)   │  │  (chat)     │
          │  N replicas │  │  N replicas  │  │  N replicas │
          └─────────────┘  └──────┬───────┘  └─────────────┘
                                  │
                     ┌────────────┼──────────────────────┐
                     ▼            ▼                       ▼
            ┌─────────────┐  ┌──────────────────┐  ┌──────────────┐
            │  Postgres + │  │  LLM provider    │  │  Redis        │
            │  pgvector   │  │                  │  │  (rate limit, │
            │  (managed)  │  │  Generation:     │  │   task queue) │
            └─────────────┘  │  Groq / vLLM /   │  └──────────────┘
                             │  Ollama (GPU VM) │
                             │                  │  ┌──────────────┐
                             │  Embeddings:     │  │  Ingestion   │
                             │  Ollama (GPU VM) │  │  workers     │
                             └──────────────────┘  └──────────────┘
```

### 2.2 LLM provider for production

The `LLM_PROVIDER` switch already exists — production is a configuration
change, not a code change.

| Use case | Recommendation |
|---|---|
| Low latency, high availability, no GPU | Groq or another managed OpenAI-compatible endpoint |
| Data sovereignty / on-premises | Dedicated GPU VM running Ollama or vLLM (`LLM_PROVIDER=ollama`) |
| Embeddings | Dedicated Ollama instance on a GPU VM — **do not change `OLLAMA_EMBEDDING_DIM`** after initial deployment without re-ingesting all documents |

### 2.3 Container images and registry

- Tag images by git SHA, push to ECR / GHCR / equivalent.
- CI builds on merge to `main`. Deployments reference a specific SHA tag —
  never `latest` — for reproducibility and clean rollback.

### 2.4 Configuration and secrets

- All `.env` values move to the deployment platform's secret manager (AWS
  Secrets Manager, ECS task environment, Kubernetes Secrets).
- `API_KEY` **must** be set to a strong random secret — the app runs with
  auth disabled when unset (correct for local dev; unacceptable in prod).
- `LLM_API_KEY` injected via secret manager, never in a committed file.
- `ALLOWED_ORIGINS` set to production frontend domain(s) only.
- `ENVIRONMENT=production`, `LOG_LEVEL=INFO`.

### 2.5 Database

- Managed Postgres with pgvector (AWS RDS for Postgres supports pgvector
  natively).
- Replace `Base.metadata.create_all()` with **Alembic migrations** — the
  single highest-priority change before production. `create_all()` cannot
  evolve an existing schema, as encountered repeatedly during development.
- Run migrations as a **pre-deploy job**, not on application startup, to
  prevent concurrent migration races across replicas.
- Enable automated backups and point-in-time recovery.
- Size `DB_POOL_SIZE` × `DB_MAX_OVERFLOW` per
  `gunicorn_workers × replica_count`, staying under `max_connections`.

### 2.6 Ingestion: decouple from API workers

`BackgroundTasks` runs ingestion in the same worker process as the upload
request. For production:

- Use a task queue (Celery + Redis, arq, or a Postgres-backed job table).
- `process_document(document_id, file_bytes)` is already queue-friendly —
  plain data in, no return value, owns its own DB session. Wrap it as a
  queue task with no changes to internals.
- Store uploaded file bytes in S3 (or equivalent) rather than passing them
  in-memory, so workers on different hosts can retrieve them.
- Scale ingestion workers independently from API workers.

### 2.7 Rate limiting at scale

The current `RateLimitMiddleware` is in-process per-worker. Effective limit
across a deployment is `configured_limit × workers × replicas`.

- Replace the in-memory `_hits` dict with Redis (`INCR` + `EXPIRE` per
  client IP per window). The `dispatch()` interface stays the same.
- Add load-balancer-level rate limiting (AWS WAF, Nginx `limit_req`) as a
  first line of defence.

### 2.8 Logging and observability

- Swap the log formatter to JSON (`python-json-logger`) for log aggregation
  platforms (CloudWatch, Loki, Datadog) — isolated change to
  `app/core/logging_config.py`.
- Every error response includes `request_id` — ensure the log platform
  indexes this field.
- Add Prometheus metrics via `prometheus-fastapi-instrumentator`: request
  latency, ingestion success/failure rate, LLM call latency, queue depth.
- Alert on: `/health` returning `degraded`, elevated 5xx rate, ingestion
  failure rate above threshold, LLM provider error rate.

### 2.9 Networking and TLS

- TLS terminates at the load balancer. Internal traffic stays in the private
  VPC.
- `RequestIDMiddleware` preserves inbound `X-Request-ID` from the LB —
  configure the LB to set this header for end-to-end correlation.

### 2.10 Authentication

The shared `API_KEY` is a deliberate trade-off for this assessment (no user
accounts). For production with real users:

- Per-user JWTs issued after login against an identity provider.
- Applied via a `Depends`-based dependency — same shape as `require_api_key`,
  route signatures unchanged.
- Move browser-side write calls (upload, delete) to server-side Next.js API
  routes so no secrets appear in the client bundle.

### 2.11 Rollout strategy

- Rolling updates (ECS / Kubernetes) with `/health` checks gating traffic
  shift.
- Alembic migrations run as a pre-deploy job, before new instances start.
- `down -v` (destructive DB wipe) is a local-dev-only operation — never run
  against production.

### 2.12 Priority order for productionizing

| Priority | Change | Why first |
|---|---|---|
| 1 | Alembic migrations | Schema changes are currently destructive without them |
| 2 | Secret management + set `API_KEY` + restrict `ALLOWED_ORIGINS` | Must be hardened before any public exposure |
| 3 | Stable LLM endpoint (Groq in prod or dedicated GPU VM) | Dev Ollama host is not a reliable production dependency |
| 4 | JSON logging + Prometheus metrics + alerting | Can't operate what you can't observe |
| 5 | Task queue for ingestion | Decouples load, enables retries, unblocks API scaling |
| 6 | Redis-backed rate limiting | Correctness requires shared state across workers/replicas |
| 7 | Per-user JWT authentication | Required before handling real user data |