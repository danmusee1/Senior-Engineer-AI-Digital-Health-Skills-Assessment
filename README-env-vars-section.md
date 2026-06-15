## Environment Variables

This project uses multiple `.env` files, each scoped to a different
service. **The root `.env` is the one used by `docker-compose.yaml`** and
is the source of truth for the containerized setup described above.

### Root `.env` (used by Docker Compose)

Copy `.env.example` to `.env` at the project root before running
`docker compose up`. This file is injected into the `backend`, `frontend`,
and `relational_db` containers via `env_file`.

```dotenv
# =========================================================================
# Postgres (relational_db)
# =========================================================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres

# =========================================================================
# Backend (app/core/config.py — Settings)
# =========================================================================
ENVIRONMENT=development
LOG_LEVEL=INFO

# Must match POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB above.
# Host = compose service name "relational_db" (not "localhost" — containers
# reach each other by service name, not via the host's loopback address).
DATABASE_URL=postgresql://postgres:postgres@relational_db:5432/postgres
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT_SECONDS=30
DB_POOL_RECYCLE_SECONDS=1800

# Ollama runs on the HOST machine, not in a container. "localhost" from
# inside the backend container refers to the container itself, so it must
# NOT be used here.
#
#   Docker Desktop (Windows/Mac): http://host.docker.internal:11434
#   Linux: http://host.docker.internal:11434
#     (requires the extra_hosts mapping already set in docker-compose.yaml)
#   Linux fallback: http://172.17.0.1:11434
#     (confirm with: docker network inspect bridge | grep Gateway)
#
# Ollama must also be started with OLLAMA_HOST=0.0.0.0 so it accepts
# connections from containers, not just 127.0.0.1.
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIM=768
OLLAMA_REQUEST_TIMEOUT_SECONDS=60.0
OLLAMA_GENERATE_TIMEOUT_SECONDS=120.0
OLLAMA_MAX_RETRIES=3
OLLAMA_RETRY_BACKOFF_SECONDS=1.0

# =========================================================================
# LLM provider switch
# =========================================================================
# Controls which backend handles generation and embeddings.
#
#   "ollama"            — use the OLLAMA_* settings above (default, fully
#                         local, no API key needed).
#   "openai_compatible" — call any OpenAI-compatible /chat/completions
#                         endpoint: Groq, OpenRouter, Together, a self-
#                         hosted vLLM/TGI server, etc.
#
# Recommended free option: Groq (https://console.groq.com — no credit card).
# The /health endpoint will report which provider is active and whether it
# is reachable.
#
# To use Ollama only (fully local, no key needed):
#   LLM_PROVIDER=ollama
#   EMBEDDING_PROVIDER=ollama
#   (leave all LLM_API_* and EMBEDDING_API_* blank)
#
# To use Groq for generation + Ollama for embeddings:
#   LLM_PROVIDER=openai_compatible
#   LLM_API_BASE_URL=https://api.groq.com/openai/v1
#   LLM_API_KEY=gsk_your_groq_key_here
#   LLM_API_MODEL=llama-3.1-8b-instant   # or llama-3.3-70b-versatile
#   EMBEDDING_PROVIDER=ollama             # Groq has no embeddings endpoint
#
# Note: EMBEDDING_PROVIDER="openai_compatible" requires a provider that
# serves an /embeddings endpoint AND whose output dimension matches
# OLLAMA_EMBEDDING_DIM (768). Mismatching dimensions will break the
# pgvector similarity search — a DB migration would be required.
LLM_PROVIDER=ollama
LLM_API_BASE_URL=
LLM_API_KEY=
LLM_API_MODEL=

EMBEDDING_PROVIDER=ollama
EMBEDDING_API_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_API_MODEL=

CHUNK_SIZE=500
CHUNK_OVERLAP=50
RETRIEVAL_TOP_K=3
MAX_UPLOAD_SIZE_MB=20

# Leave blank for local/dev (auth disabled on upload/delete).
# Set a real secret for any non-local deployment.
API_KEY=

# Comma-separated. Include every origin that calls the API directly from a
# browser (frontend, Chainlit if browser-facing).
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:6100

RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60

# =========================================================================
# Frontend (Next.js) — runtime env var injected by compose
# =========================================================================
# Server-to-server URL (Next.js server code -> backend, within Docker network)
BACKEND_URL=http://backend:6100
```

> **Note on `NEXT_PUBLIC_*` variables**: Next.js inlines `NEXT_PUBLIC_*`
> variables into the client bundle **at build time**. Setting them in the
> root `.env` has no effect on the built frontend — they must be present in
> `frontend/.env` when `npm run build` runs (see below).

### `backend/.env` (local development without Docker only)

This file is **not used** by `docker compose up` — the backend container
gets its configuration entirely from the root `.env` via `env_file`. Use
this only if you're running the backend directly with `uvicorn`/`gunicorn`
on your host, outside Docker:

```dotenv
ENVIRONMENT=development
LOG_LEVEL=INFO

# When running outside Docker, Postgres is reached via localhost (assuming
# the relational_db container's port is published to the host, as it is by
# default).
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres

# When running outside Docker, Ollama IS on localhost.
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIM=768

# Provider switch — same options as the root .env above.
# Defaults to fully local Ollama; paste a Groq key to use cloud generation.
LLM_PROVIDER=ollama
LLM_API_BASE_URL=
LLM_API_KEY=
LLM_API_MODEL=

EMBEDDING_PROVIDER=ollama
EMBEDDING_API_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_API_MODEL=

API_KEY=
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

### `frontend/.env` (build-time, browser-visible)

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:6100
```

Used by client-side code (e.g. the Upload and Chat pages) to call the
backend's published port directly from the browser. Must be set before
`npm run build` / `docker compose build frontend` for changes to take
effect.

### `chainlit_app/.env`

```dotenv
BACKEND_URL=http://backend:6100
```

Server-side only — Chainlit's Python backend calls the FastAPI backend by
its Docker service name, within the Docker network.

---

**Quick reference — which `.env` to edit:**

| I want to change... | Edit |
|---|---|
| Database credentials, Ollama URL, rate limits, API key, CORS | root `.env` |
| Switch from Ollama to Groq (or another cloud LLM) | root `.env` — set `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_API_MODEL` |
| The backend's behavior when run outside Docker | `backend/.env` |
| A URL the browser calls directly (e.g. `NEXT_PUBLIC_API_URL`) | `frontend/.env`, then rebuild the frontend image |
| Chainlit's backend URL | `chainlit_app/.env` |