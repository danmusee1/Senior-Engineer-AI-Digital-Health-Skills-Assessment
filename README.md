## Documentation

This repository contains several documents aimed at different audiences:

| Document | Purpose |
|----------|---------|
| README.md | Quick start guide for running the application locally |
| ARCHITECTURE.md | System architecture, design decisions, and trade-offs |
| ENVIRONMENT.md | Complete reference for all environment variables and configuration files |
| SETUP_AND_DEPLOYMENT.md | Production deployment and operational guidance |
| DOCUMENTATION_LAYOUT.md | Documentation structure, reading order, and maintenance guidelines |

**Recommended reading order for new users:**

1. README.md
2. ENVIRONMENT.md (if configuration changes are needed)
3. ARCHITECTURE.md
4. SETUP_AND_DEPLOYMENT.md

For details on how the documentation is organized and why content is split across files, see `DOCUMENTATION_LAYOUT.md`.
## Getting Started

### Prerequisites

- Docker and Docker Compose
- [Ollama](https://ollama.com) installed and running on the **host machine**
  (not in a container), with the required models pulled:

  ```sh
  ollama pull llama3.2:latest
  ollama pull nomic-embed-text
  ```

  Ollama must be reachable from inside the containers, which means it needs
  to listen on all interfaces, not just `127.0.0.1`:

  ```sh
  OLLAMA_HOST=0.0.0.0 ollama serve
  ```

  (If running Ollama as a systemd service, set `OLLAMA_HOST=0.0.0.0` in its
  environment and restart the service.)

### Setup

1. **Copy and configure environment variables:**

   ```sh
   cp .env.example .env
   ```

   At minimum, confirm `OLLAMA_BASE_URL` matches your platform:

   | Platform | `OLLAMA_BASE_URL` |
   |---|---|
   | Docker Desktop (Windows/Mac) | `http://host.docker.internal:11434` |
   | Linux | `http://host.docker.internal:11434` (requires the `extra_hosts` mapping already set in `docker-compose.yaml`) |
   | Linux fallback | `http://172.17.0.1:11434` — confirm with `docker network inspect bridge \| grep Gateway` |

2. **Build and start all services:**

   ```sh
   docker compose -p assessment up -d --build
   ```

3. **Access the application:**

   | Service | URL |
   |---|---|
   | Frontend / **Instructions** | [http://localhost:3000](http://localhost:3000) |
   | Chainlit (Chat UI) | [http://localhost:8000](http://localhost:8000) |
   | Backend (API) | [http://localhost:6100](http://localhost:6100) |
   | Backend health check | [http://localhost:6100/health](http://localhost:6100/health) |
   | Database (PostgreSQL) | `localhost:5432` |

   Open [http://localhost:3000](http://localhost:3000) in your browser to read the full assessment requirements.

4. **Verify everything is healthy:**

   ```sh
   curl http://localhost:6100/health
   ```

   Expected response:

   ```json
   {"status": "ok", "database": true, "ollama": true}
   ```

   If `"ollama": false`, double-check `OLLAMA_BASE_URL` in `.env` and that
   Ollama is bound to `0.0.0.0`, then:

   ```sh
   docker compose -p assessment up -d --force-recreate backend
   ```

5. **Using the app:**

   - Go to the **Upload** page and upload a PDF (max 20MB). Ingestion runs
     in the background — the document list shows status (`pending` →
     `processing` → `completed`/`failed`) and updates automatically.
   - Go to the **Chat** page (or Chainlit) and ask questions once a document
     shows `completed`. Answers include source chunks with similarity
     scores.

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

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot assign requested address` calling Ollama | Backend container can't reach `localhost:11434` (that's the container itself, not the host) | Set `OLLAMA_BASE_URL=http://host.docker.internal:11434` and ensure Ollama runs with `OLLAMA_HOST=0.0.0.0` |
| `invalid input value for enum document_status` | Stale Postgres schema from a previous version | `docker compose -p assessment down -v` then `up -d --build` (dev only — destroys data) |
| `service "backend" is not running` when running `docker compose exec` | Missing `-p assessment` project flag | Re-run with `docker compose -p assessment exec backend ...` |
| Document stuck on `processing` | Background ingestion failed | Check `error_message` via `GET /rag/documents/{id}` and `docker compose -p assessment logs backend` |

### Further Reading

- `ARCHITECTURE.md` — design decisions and trade-offs
- `ENVIRONMENT.md` — complete environment variable reference
- `SETUP_AND_DEPLOYMENT.md` — production deployment plan
- `DOCUMENTATION_LAYOUT.md` — documentation structure and recommended reading order

If you're new to the project, start with this README and then follow the
recommended reading order in `DOCUMENTATION_LAYOUT.md`.

---