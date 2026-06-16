# Last Mile Health — RAG Document Q&A System

A Retrieval-Augmented Generation (RAG) system for document Q&A. Upload PDF
documents, ask questions, and receive answers grounded in the document
content with source citations. Built with FastAPI, Next.js, Chainlit, and
Postgres + pgvector.

---

## Documentation

| Document | Purpose |
|---|---|
| `README.md` | Quick start guide for running the application locally |
| `ARCHITECTURE.md` | System architecture, design decisions, and trade-offs |
| `ENVIRONMENT.md` | Complete reference for all environment variables |
| `SETUP_AND_DEPLOYMENT.md` | Production deployment and operational guidance |

**Recommended reading order:**
1. `README.md` — you are here
2. `ENVIRONMENT.md` — if you need to change configuration
3. `ARCHITECTURE.md` — to understand design decisions
4. `SETUP_AND_DEPLOYMENT.md` — before any non-local deployment

---

## Architecture at a Glance

```
Browser
  │
  ├── Frontend (Next.js)  :3000  ──┐
  └── Chainlit (Chat UI)  :8000  ──┤
                                    │
                                    ▼
                          Backend API (FastAPI) :6100
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                                   ▼
     Postgres + pgvector :5432            LLM provider (your choice)
     (documents, chunks,                  │
      embeddings)                         ├── Option A: Groq (cloud, free)
                                          └── Option B: Ollama (local, no key)
```

For design decisions and trade-offs, see `ARCHITECTURE.md`.

---

## Prerequisites

Before running anything, you need:

- **Docker and Docker Compose** — [install Docker](https://docs.docker.com/get-docker/)
- **An LLM provider** — choose one of the two options below

> **Embeddings always run via Ollama** regardless of which LLM provider you
> choose (Groq has no embeddings endpoint). So Ollama is required in both
> cases — the difference is only where text *generation* happens.

---

## Step 1 — Choose your LLM provider and install prerequisites

### Option A — Groq (recommended for a quick demo, no GPU needed)

Groq is free, requires no credit card, and is significantly faster than
running a local model.

1. Sign up at [console.groq.com](https://console.groq.com) and create an
   API key.
2. Install [Ollama](https://ollama.com) on the **host machine** (for
   embeddings only) and pull the embedding model:

   ```sh
   ollama pull nomic-embed-text
   ```

3. Start Ollama bound to all interfaces so containers can reach it:

   ```sh
   OLLAMA_HOST=0.0.0.0 ollama serve
   ```

   > If running Ollama as a systemd service, set `OLLAMA_HOST=0.0.0.0` in
   > its environment file and restart it.

### Option B — Ollama only (fully local, no API key needed)

All generation and embeddings run on your machine. Requires a GPU or
patience — `llama3.2` is several GB and generation will be slow on CPU.

1. Install [Ollama](https://ollama.com) on the **host machine** and pull
   both models:

   ```sh
   ollama pull llama3.2:latest
   ollama pull nomic-embed-text
   ```

2. Start Ollama bound to all interfaces:

   ```sh
   OLLAMA_HOST=0.0.0.0 ollama serve
   ```

---

## Step 2 — Configure environment variables

```sh
cp .env.example .env
```

Then open `.env` and make the following changes depending on your chosen
provider:

### If using Groq (Option A)

```dotenv
# LLM — use Groq
LLM_PROVIDER=openai_compatible
LLM_API_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk_your_key_here        # ← paste your Groq API key
LLM_API_MODEL=llama-3.1-8b-instant

# Embeddings — stay on Ollama (Groq has no embeddings endpoint)
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434   # ← see table below
```

### If using Ollama only (Option B)

```dotenv
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434   # ← see table below
OLLAMA_MODEL=llama3.2:latest
```

### `OLLAMA_BASE_URL` — platform-specific values

`localhost` inside a container refers to the container itself, not your
host machine. Use one of these instead:

| Platform | `OLLAMA_BASE_URL` |
|---|---|
| Docker Desktop (Windows / Mac) | `http://host.docker.internal:11434` |
| Linux | `http://host.docker.internal:11434` — requires `extra_hosts` mapping already set in `docker-compose.yaml` |
| Linux fallback | Find your bridge IP: `docker network inspect bridge \| grep Gateway` then use `http://<that-ip>:11434` |

> **Security note**: Never commit real API keys to version control. Add
> `.env` to `.gitignore` (it already is) and keep secrets out of
> screenshots, chat logs, and documentation.

---

## Step 3 — Build and start all services

```sh
docker compose -p assessment up -d --build
```

This starts four containers:

| Container | Purpose | Port |
|---|---|---|
| `backend` | FastAPI RAG API | `6100` |
| `frontend` | Next.js upload + chat UI | `3000` |
| `chainlit` | Chainlit chat interface | `8000` |
| `relational_db` | Postgres 16 + pgvector | `5432` |

---

## Step 4 — Verify everything is healthy

```sh
curl http://localhost:6100/health
```

**Expected response (Groq):**
```json
{"status": "ok", "database": true, "llm": true, "llm_provider": "openai_compatible"}
```

**Expected response (Ollama):**
```json
{"status": "ok", "database": true, "llm": true, "llm_provider": "ollama"}
```

If `"llm": false` with **Groq** — check that `LLM_API_KEY` is set and
valid in `.env`, then:

```sh
docker compose -p assessment up -d --force-recreate backend
```

If `"llm": false` with **Ollama** — check that `OLLAMA_BASE_URL` matches
your platform (see table above) and Ollama is running with
`OLLAMA_HOST=0.0.0.0`, then force-recreate the backend as above.

---

## Step 5 — Use the app

| Service | URL |
|---|---|
| Frontend (Upload + Chat) | [http://localhost:3000](http://localhost:3000) |
| Chainlit (Chat UI) | [http://localhost:8000](http://localhost:8000) |
| Backend API | [http://localhost:6100](http://localhost:6100) |
| API health check | [http://localhost:6100/health](http://localhost:6100/health) |
| API docs (Swagger) | [http://localhost:6100/docs](http://localhost:6100/docs) |

1. Go to [http://localhost:3000/upload](http://localhost:3000/upload)
2. Upload a PDF (max 20 MB). Ingestion runs in the background — watch the
   status badge change from `pending` → `processing` → `completed`.
3. Once `completed`, go to [http://localhost:3000/chat](http://localhost:3000/chat)
   and ask a question. Answers include source chunks with similarity scores.

---

## Stopping services

```sh
docker compose -p assessment down
```

To also wipe the database (use this if you hit a stale-schema error during
development — **this deletes all uploaded documents**):

```sh
docker compose -p assessment down -v
```

---

## Running tests

### Backend

No Postgres or LLM provider needed — all external calls are mocked.

```sh
docker compose -p assessment exec backend pytest tests/test_routes.py -v  
docker compose -p assessment up -d relational_db
cd backend
pip install -r requirements.txt
pytest -v
```

### Frontend

```sh
cd frontend
npm install
npx jest
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `"llm": false` in `/health` (Groq) | Missing or invalid `LLM_API_KEY` | Paste a valid key from [console.groq.com](https://console.groq.com) into `.env`; recreate backend |
| `"llm": false` in `/health` (Ollama) | Ollama unreachable from container | Check `OLLAMA_BASE_URL` matches your platform; ensure `OLLAMA_HOST=0.0.0.0`; recreate backend |
| `Cannot assign requested address` | `OLLAMA_BASE_URL=http://localhost:11434` used inside container | Change to `http://host.docker.internal:11434` in `.env` |
| `invalid input value for enum document_status` | Stale Postgres schema from a previous version | `docker compose -p assessment down -v` then `up -d --build` (dev only — destroys data) |
| `service "backend" is not running` on `exec` | Missing `-p assessment` project flag | Re-run with `docker compose -p assessment exec backend ...` |
| Document stuck on `processing` | Background ingestion failed | Check `GET /rag/documents/{id}` for `error_message`; check `docker compose -p assessment logs backend` |
| Upload returns duplicate but document is `failed` | Previous attempt failed after the record was created | Delete via `DELETE /rag/documents/{id}` (or wipe the DB), then re-upload |

---

## Further reading

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — design decisions and trade-offs
- [`ENVIRONMENT.md`](./ENVIRONMENT.md) — full annotated `.env` reference
- [`SETUP_AND_DEPLOYMENT.md`](./SETUP_AND_DEPLOYMENT.md) — production deployment plan