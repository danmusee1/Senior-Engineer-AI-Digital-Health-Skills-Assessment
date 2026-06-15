## Documentation

This repository contains several documents aimed at different audiences:

| Document                | Purpose                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| README.md               | Quick start guide for running the application locally                    |
| ARCHITECTURE.md         | System architecture, design decisions, and trade-offs                    |
| ENVIRONMENT.md          | Complete reference for all environment variables and configuration files |
| SETUP_AND_DEPLOYMENT.md | Production deployment and operational guidance                           |
| DOCUMENTATION_LAYOUT.md | Documentation structure, reading order, and maintenance guidelines       |

**Recommended reading order for new users:**

1. README.md
2. ENVIRONMENT.md (if configuration changes are needed)
3. ARCHITECTURE.md
4. SETUP_AND_DEPLOYMENT.md

For details on how the documentation is organized and why content is split across files, see `DOCUMENTATION_LAYOUT.md`.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- A language model backend — choose **one** of the options below:

  **Option A — Groq (recommended for a quick demo, no GPU needed)**
  1. Sign up at [console.groq.com](https://console.groq.com) — free, no credit card required.
  2. Create an API key.
  3. In your `.env` set:

```dotenv
     LLM_PROVIDER=openai_compatible
     LLM_API_BASE_URL=https://api.groq.com/openai/v1
     LLM_API_KEY=gsk_your_key_here
     LLM_API_MODEL=llama-3.1-8b-instant
     EMBEDDING_PROVIDER=ollama   # Groq has no embeddings endpoint
```

4. Still install Ollama (see Option B) and pull **only** the embedding model:

```sh
     ollama pull nomic-embed-text
     OLLAMA_HOST=0.0.0.0 ollama serve
```

**Option B — Ollama (fully local, no API key)**

Install [Ollama](https://ollama.com) on the **host machine** (not in a
container) and pull the required models:

```sh
  ollama pull llama3.2:latest
  ollama pull nomic-embed-text
```

Ollama must listen on all interfaces so containers can reach it:

```sh
  OLLAMA_HOST=0.0.0.0 ollama serve
```

(If running Ollama as a systemd service, set `OLLAMA_HOST=0.0.0.0` in its
environment and restart the service.)

In your `.env` make sure the provider switch is set to its default:

```dotenv
  LLM_PROVIDER=ollama
  EMBEDDING_PROVIDER=ollama
```

### Setup

1. **Copy and configure environment variables:**

```sh
   cp .env.example .env
```

**If using Groq (Option A):** paste your API key into `LLM_API_KEY` and
confirm `LLM_PROVIDER=openai_compatible`. Also confirm `OLLAMA_BASE_URL`
below — it is still used for embeddings.

**If using Ollama only (Option B):** confirm `OLLAMA_BASE_URL` matches
your platform and that `LLM_PROVIDER=ollama`:

| Platform                     | `OLLAMA_BASE_URL`                                                                                             |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Docker Desktop (Windows/Mac) | `http://host.docker.internal:11434`                                                                           |
| Linux                        | `http://host.docker.internal:11434` (requires the `extra_hosts` mapping already set in `docker-compose.yaml`) |
| Linux fallback               | `http://172.17.0.1:11434` — confirm with `docker network inspect bridge \| grep Gateway`                      |

2. **Build and start all services:**

```sh
   docker compose -p assessment up -d --build
```

3. **Access the application:**

   | Service                     | URL                                                          |
   | --------------------------- | ------------------------------------------------------------ |
   | Frontend / **Instructions** | [http://localhost:3000](http://localhost:3000)               |
   | Chainlit (Chat UI)          | [http://localhost:8000](http://localhost:8000)               |
   | Backend (API)               | [http://localhost:6100](http://localhost:6100)               |
   | Backend health check        | [http://localhost:6100/health](http://localhost:6100/health) |
   | Database (PostgreSQL)       | `localhost:5432`                                             |

   Open [http://localhost:3000](http://localhost:3000) in your browser to read the full assessment requirements.

4. **Verify everything is healthy:**

```sh
   curl http://localhost:6100/health
```

Expected response (Groq):

```json
{
  "status": "ok",
  "database": true,
  "llm": true,
  "llm_provider": "openai_compatible"
}
```

Expected response (Ollama):

```json
{ "status": "ok", "database": true, "llm": true, "llm_provider": "ollama" }
```

If `"llm": false` with Groq, check that `LLM_API_KEY` is set correctly in `.env`.

If `"llm": false` with Ollama, double-check `OLLAMA_BASE_URL` and that
Ollama is bound to `0.0.0.0`, then:

```sh
   docker compose -p assessment up -d --force-recreate backend
```

5. **Using the app:**
   - Go to the **Upload** page and upload a PDF (max 20MB). Ingestion runs
     in the background — the document list shows status (`pending` →
     `processing` → `completed`/`failed`) and updates automatically.
   - Go to the **Chat** page (or Chainlit) and ask questions once a document
     shows `completed`. Answers include source chunks with similarity scores.

### Stopping services

```sh
docker compose -p assessment down
```

To also wipe the database (useful if you hit a stale-schema error during
development):

```sh
docker compose -p assessment down -v
```

### Troubleshooting

| Symptom                                                               | Cause                                                                                       | Fix                                                                                                       |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `"llm": false` in `/health` with Groq                                 | Missing or invalid `LLM_API_KEY`                                                            | Paste a valid key from [console.groq.com](https://console.groq.com) into `.env` and recreate the backend  |
| `Cannot assign requested address` calling Ollama                      | Backend container can't reach `localhost:11434` (that's the container itself, not the host) | Set `OLLAMA_BASE_URL=http://host.docker.internal:11434` and ensure Ollama runs with `OLLAMA_HOST=0.0.0.0` |
| `"llm": false` in `/health` with Ollama                               | Ollama not reachable from inside the container                                              | Check `OLLAMA_BASE_URL` and that `OLLAMA_HOST=0.0.0.0` is set, then recreate the backend                  |
| `invalid input value for enum document_status`                        | Stale Postgres schema from a previous version                                               | `docker compose -p assessment down -v` then `up -d --build` (dev only — destroys data)                    |
| `service "backend" is not running` when running `docker compose exec` | Missing `-p assessment` project flag                                                        | Re-run with `docker compose -p assessment exec backend ...`                                               |
| Document stuck on `processing`                                        | Background ingestion failed                                                                 | Check `error_message` via `GET /rag/documents/{id}` and `docker compose -p assessment logs backend`       |

### Further Reading

- `ARCHITECTURE.md` — design decisions and trade-offs
- `ENVIRONMENT.md` — complete environment variable reference
- `SETUP_AND_DEPLOYMENT.md` — production deployment plan
- `DOCUMENTATION_LAYOUT.md` — documentation structure and recommended reading order

If you're new to the project, start with this README and then follow the
recommended reading order in `DOCUMENTATION_LAYOUT.md`.

---
