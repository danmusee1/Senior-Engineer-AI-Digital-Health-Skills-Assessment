# Architecture & Design Decisions

This document records the notable architectural decisions and trade-offs in
the Last Mile Health RAG API, why they were made, and what would change if
the system's scale or requirements grow.

## Overview

A FastAPI backend implementing Retrieval-Augmented Generation over uploaded
PDFs: documents are chunked, embedded (via Ollama), and stored in Postgres
with `pgvector`; queries retrieve the nearest chunks by cosine similarity
and feed them to a local LLM (also via Ollama) to produce a grounded answer.

```
Client → CORS → RateLimit → RequestID → Routes → Service → (Postgres / Ollama)
```

## 1. Configuration: centralized via `pydantic-settings`

All tunables (`app/core/config.py`) are read from environment variables /
`.env` into a single `Settings` object, cached with `lru_cache`. This avoids
scattered `os.getenv()` calls, documents every configurable value with a
default, and makes deploying to a new environment a matter of setting env
vars rather than hunting through source.

**Trade-off**: a single settings object constructed at import time means
tests must set environment variables *before* importing any `app.*` module
(see `conftest.py`). This is a minor inconvenience for a meaningful
simplification elsewhere.

## 2. Authentication: shared API key on write endpoints

`app/core/security.py` implements a single shared-secret `X-API-Key` header,
enforced via `require_api_key` only on `/rag/upload` and
`/rag/documents/{id}` (DELETE). Read endpoints (`/rag/query`,
`/rag/documents`, `/health`) are open.

- If `API_KEY` is unset, auth is skipped entirely (local/dev convenience).
- If set, every protected request must present a matching key, compared
  with `hmac.compare_digest` to avoid timing side-channels.

**Trade-off**: a single shared secret gives no per-user accountability and
cannot be revoked for one client without rotating it for everyone. This
assessment has no user accounts, so a full OAuth/JWT system would be
over-engineering. For a system with real user accounts, replace this with
per-user JWTs issued after login against an identity provider, applied via
the same `Depends(require_api_key)`-shaped dependency so route signatures
don't need to change.

## 3. Ingestion: async background processing with status tracking

`POST /rag/upload` validates the file (magic bytes, size, content-type),
creates a `Document` row with `status=pending`, and returns immediately.
Text extraction, chunking, embedding, and storage happen in
`process_document`, run via FastAPI's `BackgroundTasks`.

Document status (`pending → processing → completed → failed`) is persisted
on the row, with `error_message` populated on failure. `process_document`
catches all exceptions internally — it must never raise, since
`BackgroundTasks` does not surface exceptions to the client, and an
unhandled exception there would otherwise be an untraceable silent failure.

Query retrieval (`query_rag`) only considers chunks belonging to
`status=completed` documents, so a document mid-ingestion (or one that
failed partway through) never contributes partial/inconsistent context.

**Trade-off**: `BackgroundTasks` runs in-process, in the same worker that
handled the request. For high ingestion volume, this competes with request
handling threads/workers. A dedicated task queue (Celery, arq, or a simple
Postgres-backed job table polled by a worker process) would decouple
ingestion load from API latency — the `process_document(document_id,
file_bytes)` function signature is already queue-friendly (plain data in,
nothing returned, own DB session) and could be wrapped as a queue task with
minimal change.

## 4. Deduplication: content-hash based, with DB-level race safety

Every upload is hashed (SHA-256 of raw bytes). If a `Document` with the same
`content_hash` already exists, the existing record is returned
(`is_duplicate=true`) and no new ingestion is triggered — protecting against
double-submits, retried requests after network blips, and genuine
re-uploads of the same file under a different name.

The hash column has a unique constraint at the database level. The
check-then-insert in `create_document_record` has a classic TOCTOU race
under concurrent identical uploads; if the `INSERT` violates the unique
constraint, the code rolls back and re-queries for the row the *other*
request created, returning that as the duplicate. The database is the final
authority, not the initial SELECT.

## 5. Chunking: fixed-size character splitter with overlap

`chunk_text` splits extracted PDF text into fixed-size, overlapping chunks
(default 500 chars, 50 overlap). This is simple, deterministic, and fast —
important for a pipeline that may process many documents — but it can split
mid-sentence. The overlap exists specifically so a fact split across a
boundary still appears in full in at least one chunk.

**Trade-off / next step**: a sentence/paragraph-aware splitter (e.g.
LangChain's `RecursiveCharacterTextSplitter`) would likely improve answer
quality by keeping semantically coherent units together, at the cost of
slightly more complex, less predictable chunk boundaries. Reasonable next
step if retrieval quality becomes a concern.

## 6. Ollama integration: retries with exponential backoff

All Ollama calls (`get_embedding`, `get_embeddings_batch`,
`generate_response`) go through `_post_with_retry`, which retries on
transient failures (connection errors, timeouts, 5xx) with exponential
backoff, up to `OLLAMA_MAX_RETRIES`. 4xx responses are not retried, since
those indicate a malformed request on our side.

`get_embeddings_batch` prefers Ollama's batch `/api/embed` endpoint
(embedding many chunks in one round trip) and falls back to one
`/api/embeddings` call per chunk if the batch endpoint is unavailable or
returns an unexpected shape — keeping ingestion working against older
Ollama installs at the cost of more round-trips.

**Trade-off**: Ollama runs as an external process (often on the host, not
in the container — see `OLLAMA_BASE_URL` defaulting to a host-gateway IP).
It can be cold-starting, briefly OOM, or restarting; retries absorb
transient blips without failing an entire ingestion or query, but a
persistently-down Ollama will still surface as a failed document /ingestion
or a 500 on query after exhausting retries — by design, since retrying
forever would hang requests.

## 7. Request correlation: request ID middleware

`RequestIDMiddleware` assigns every request an ID (reusing an inbound
`X-Request-ID` header if present, so a load balancer / gateway ID is
preserved end-to-end), stores it on `request.state.request_id`, binds it
into the logging context for the duration of the request via
`logging.setLogRecordFactory`, and echoes it back in the response headers.

Every error response (`ErrorResponse.request_id`) includes this ID, so a
user reporting "error ref: <id>" lets an operator grep logs for every line
emitted while handling that exact request.

**Trade-off**: `setLogRecordFactory` is global mutable state, restored in a
`finally` block. Under `asyncio`, concurrent requests on the same worker
could theoretically interleave between the factory being set and a log call
happening — in practice, the window is small and request handling is mostly
sequential per-task, but a `contextvars`-based approach (binding `request_id`
into a `ContextVar` and reading it in the formatter/filter) would be more
robust under heavy concurrency and is the natural next step if this becomes
an issue.

## 8. Rate limiting: in-process fixed-window, per IP

`RateLimitMiddleware` implements a dependency-free fixed-window limiter
keyed by client IP, using a `defaultdict(deque)` of request timestamps. No
Redis or external store — the whole system runs with `docker compose up`
and nothing else.

**Trade-off**: state is held in-process.
- It resets on process restart.
- With multiple gunicorn workers or multiple replicas, each tracks its own
  counters — the *effective* limit becomes `limit × worker_count ×
  replica_count`, not the configured limit.

For a single-instance deployment (this assessment's scope) this is
acceptable and keeps the dependency footprint minimal. For production with
multiple workers/instances, replace the `_hits` store with a Redis-backed
counter (`INCR` + `EXPIRE` per IP per window), keeping the same middleware
`dispatch()` interface — no route or call-site changes required.

## 9. Logging: structured plain text, not JSON

`app/core/logging_config.py` configures a single-line format including
timestamp, level, logger name, request ID, and message. Plain text rather
than JSON.

**Trade-off**: for the team's current scale (small team, moderate traffic)
this is directly readable in `docker logs` / CloudWatch without extra
tooling. If/when this feeds a log aggregation platform (Grafana Loki,
CloudWatch Logs Insights), swapping the `Formatter` for a JSON formatter
(e.g. `python-json-logger`) is an isolated change to one file — nothing else
in the codebase needs to know about it, since all logging goes through
`logging.getLogger(__name__)` as usual.

## 10. Error responses: consistent shape, no internal detail leakage

Every error — `HTTPException`, validation errors, and unhandled exceptions
— is mapped to the same `ErrorResponse` shape (`detail`, `request_id`) via
global exception handlers in `main.py`. Unhandled exceptions are logged with
full tracebacks server-side but return a generic "Internal server error."
to the client, so stack traces and internal paths are never leaked in
production while still being fully diagnosable via the request ID.

## 11. CORS: configurable origin allowlist

`ALLOWED_ORIGINS` (comma-separated) replaces a wildcard `allow_origins=["*"]`
combined with `allow_credentials=True` — that combination is rejected by
browsers and is a known misconfiguration. The default
(`http://localhost:3000,http://localhost:8000`) covers local frontend dev;
any non-local deployment must set this explicitly.

## 12. Database: connection pooling, pgvector, migrations

Engine is created with explicit pool size, overflow, timeout, and recycle
settings (all configurable), plus `pool_pre_ping=True` so stale connections
(e.g. after a Postgres restart) are detected and replaced rather than
surfacing as query errors.

**Not yet addressed / next step**: schema changes currently rely on
`Base.metadata.create_all()` at startup, which creates missing tables but
does not alter existing ones. Adding Alembic migrations is the natural next
step before this goes to a real production environment with existing data —
the new columns added to `documents` (`content_hash`, `status`,
`chunk_count`, `error_message`, `updated_at`) would need a migration on top
of an existing deployment.

## Summary of trade-offs deferred to "next step"

| Area | Current | Production-scale alternative |
|---|---|---|
| Ingestion | In-process `BackgroundTasks` | Dedicated task queue (Celery/arq) |
| Rate limiting | In-process per-worker | Redis `INCR`+`EXPIRE` |
| Chunking | Fixed-size character splitter | Sentence/paragraph-aware splitter |
| Logging | Plain-text structured | JSON (swap formatter only) |
| Auth | Shared API key | Per-user JWT via identity provider |
| Schema changes | `create_all()` at startup | Alembic migrations |
| Request ID binding | Global `setLogRecordFactory` | `contextvars`-based |
