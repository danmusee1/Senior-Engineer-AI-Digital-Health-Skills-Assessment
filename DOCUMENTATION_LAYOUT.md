# README — Documentation Layout & Reading Order

This file explains how the project's documentation is organized so a new
user (or reviewer) knows exactly what to read, in what order, to get from
zero to a running, understood system.

---

## Suggested `README.md` structure (top to bottom)

```
README.md
│
├── 1. Project Overview          ← what this is, 2-3 sentences
├── 2. Architecture at a Glance   ← one diagram + link to ARCHITECTURE.md
├── 3. Prerequisites              ← Docker, Ollama setup (the part people skip and regret)
├── 4. Environment Variables      ← which .env to edit, link to full reference
├── 5. Getting Started            ← the actual commands to run
├── 6. Using the App              ← upload a PDF, ask a question
├── 7. Troubleshooting            ← the errors people will actually hit
├── 8. Running Tests
├── 9. Further Reading            ← links to ARCHITECTURE.md, SETUP_AND_DEPLOYMENT.md
└── 10. Project Structure         ← folder tree (optional, at the end)
```

The principle: **everything a first-time user needs to get the app running
lives in `README.md` itself**, in the order they'll need it. Deeper design
rationale and the production deployment plan are split into separate files
*linked from* the README, so the README doesn't become a 1000-line wall of
text — but nothing required for local setup forces the reader to jump
files.

---

## What goes in each section

### 1. Project Overview

2-3 sentences: what the system does (RAG over PDFs — upload, ask questions,
get grounded answers with sources), and what's included (backend API,
Next.js frontend, Chainlit chat UI, Postgres+pgvector).

### 2. Architecture at a Glance

One small diagram (text/ASCII is fine) showing:

```
Frontend (3000) ─┐
Chainlit (8000) ─┼──▶ Backend API (6100) ──▶ Postgres+pgvector (5432)
                 │                       └──▶ Ollama (host, 11434)
```

Then: *"For design decisions and trade-offs, see `ARCHITECTURE.md`."* Don't
duplicate that content here — just point to it.

### 3. Prerequisites

This is the section that prevents the most support questions. State plainly,
**before any commands**:

- Docker + Docker Compose required.
- **Ollama must be installed and running on your host machine** (not in a
  container), with `llama3.2:latest` and `nomic-embed-text` pulled, and
  started with `OLLAMA_HOST=0.0.0.0` so containers can reach it.

This is the #1 thing that breaks the app on first run if skipped — put it
first, not buried in troubleshooting.

### 4. Environment Variables

A short intro paragraph plus **one table** pointing to the right file:

| I want to change... | Edit |
|---|---|
| Database, Ollama URL, rate limits, API key, CORS | root `.env` |
| A URL the browser calls directly | `frontend/.env` (rebuild after editing) |
| Chainlit's backend URL | `chainlit_app/.env` |

Then a one-line note: *"`cp .env.example .env` to get started — see
`ENVIRONMENT.md` for the full annotated reference of every variable."*

Move the full annotated `.env` walkthrough (all four files, with comments
explaining each variable) into a separate `ENVIRONMENT.md` — that content
is reference material, not something read top-to-bottom on first setup.

### 5. Getting Started

The exact commands, in order, nothing extra:

```sh
cp .env.example .env
# edit .env: confirm OLLAMA_BASE_URL matches your platform (see Environment Variables above)

docker compose -p assessment up -d --build

curl http://localhost:6100/health
# expect: {"status": "ok", "database": true, "ollama": true}
```

Then the service URL table (frontend, chainlit, backend, db).

### 6. Using the App

3-4 lines: go to Upload, drop a PDF, wait for status `completed`, go to
Chat, ask a question, see sources.

### 7. Troubleshooting

The table of real errors and fixes (Ollama connectivity, stale enum schema,
missing `-p` flag, stuck `processing` status). Keep this in the README
itself — it's exactly what people search for when something breaks, and
having it one scroll away beats a separate file.

### 8. Running Tests

```sh
docker compose -p assessment up -d relational_db
cd backend && pip install -r requirements.txt --break-system-packages && pytest
```

One line noting Ollama calls are mocked in tests.

### 9. Further Reading

```
- ARCHITECTURE.md          — design decisions & trade-offs
- ENVIRONMENT.md           — full annotated .env reference (all 4 files)
- SETUP_AND_DEPLOYMENT.md  — production deployment plan
```

### 10. Project Structure

The folder tree, at the very bottom — useful for orientation but not needed
to get the app running, so it doesn't need to be near the top.

---

## File map (what to actually create/keep)

| File | Purpose | Audience |
|---|---|---|
| `README.md` | Everything needed to get running locally, in order | First-time user |
| `ARCHITECTURE.md` | Why things are built this way, trade-offs | Reviewer / future maintainer |
| `ENVIRONMENT.md` | Every `.env` variable across all 4 files, annotated | Anyone configuring a specific deployment |
| `SETUP_AND_DEPLOYMENT.md` | Production deployment plan | Whoever deploys this for real |

This keeps the README focused and linear (read top to bottom, run the
commands, it works), while the deeper reference material is one click away
for anyone who needs it — without forcing every reader through it first.
