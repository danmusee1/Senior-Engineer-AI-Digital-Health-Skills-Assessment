"""
Core RAG service: validation, ingestion, retrieval, and generation.

This module deliberately contains no FastAPI-specific code (no Request,
HTTPException, etc.) — it's plain Python that operates on SQLAlchemy
sessions and raw bytes, so it can be unit-tested without spinning up the
API, and can be called from a background task, a CLI, or a future worker
process without modification.
"""

from __future__ import annotations

import hashlib
import io
import logging
import time

import httpx
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)

PDF_MAGIC_BYTES = b"%PDF-"


# ---------------------------------------------------------------------------
# Validation & hashing
# ---------------------------------------------------------------------------


def compute_file_hash(file_bytes: bytes) -> str:
    """SHA-256 hex digest of the raw file bytes, used for deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()


def looks_like_pdf(file_bytes: bytes) -> bool:
    """Check the PDF magic number, independent of the declared content-type."""
    return file_bytes[:5] == PDF_MAGIC_BYTES


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_text(
    raw_text: str,
    size: int = settings.chunk_size,
    overlap: int = settings.chunk_overlap,
) -> list[str]:
    """Split text into overlapping fixed-size chunks."""
    if size <= overlap:
        raise ValueError("chunk size must be greater than chunk overlap")

    chunks: list[str] = []
    start = 0
    text_length = len(raw_text)
    while start < text_length:
        end = start + size
        chunk = raw_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Ollama client helpers (with retries) // compatible with OpenAI-style APIs if configured
# ---------------------------------------------------------------------------


# def _post_with_retry(url: str, json: dict, timeout: float) -> httpx.Response:
#     """POST to Ollama with retries and exponential backoff."""
#     last_exc: Exception | None = None
#     for attempt in range(1, settings.ollama_max_retries + 1):
#         try:
#             response = httpx.post(url, json=json, timeout=timeout)
#             if response.status_code >= 500:
#                 response.raise_for_status()
#             return response
#         except (httpx.TransportError, httpx.HTTPStatusError) as exc:
#             last_exc = exc
#             if attempt < settings.ollama_max_retries:
#                 backoff = settings.ollama_retry_backoff_seconds * (2 ** (attempt - 1))
#                 logger.warning(
#                     "Ollama request to %s failed (attempt %d/%d): %s. Retrying in %.1fs.",
#                     url,
#                     attempt,
#                     settings.ollama_max_retries,
#                     exc,
#                     backoff,
#                 )
#                 time.sleep(backoff)
#             else:
#                 logger.error(
#                     "Ollama request to %s failed after %d attempts: %s",
#                     url,
#                     settings.ollama_max_retries,
#                     exc,
#                 )
#     assert last_exc is not None
#     raise last_exc
def _post_with_retry(
    url: str,
    json: dict,
    timeout: float,
    headers: dict | None = None,
) -> httpx.Response:
    """POST with retries and exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(1, settings.ollama_max_retries + 1):
        try:
            response = httpx.post(url, json=json, headers=headers, timeout=timeout)
            if response.status_code >= 500:
                response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < settings.ollama_max_retries:
                backoff = settings.ollama_retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s. Retrying in %.1fs.",
                    url,
                    attempt,
                    settings.ollama_max_retries,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
            else:
                logger.error(
                    "Request to %s failed after %d attempts: %s",
                    url,
                    settings.ollama_max_retries,
                    exc,
                )
    assert last_exc is not None
    raise last_exc

# def get_embedding(text_input: str) -> list[float]:
#     """Get a single embedding vector from Ollama."""
#     response = _post_with_retry(
#         f"{settings.ollama_base_url}/api/embeddings",
#         json={"model": settings.ollama_embedding_model, "prompt": text_input},
#         timeout=settings.ollama_request_timeout_seconds,
#     )
#     response.raise_for_status()
#     return response.json()["embedding"]


# def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
#     """Get embeddings for multiple chunks, batching where the API allows it."""
#     if not texts:
#         return []

#     try:
#         response = _post_with_retry(
#             f"{settings.ollama_base_url}/api/embed",
#             json={"model": settings.ollama_embedding_model, "input": texts},
#             timeout=settings.ollama_request_timeout_seconds,
#         )
#         response.raise_for_status()
#         embeddings = response.json().get("embeddings")
#         if embeddings and len(embeddings) == len(texts):
#             return embeddings
#         logger.warning(
#             "Batch embedding endpoint returned unexpected shape; "
#             "falling back to per-chunk embedding calls."
#         )
#     except (httpx.HTTPStatusError, httpx.TransportError, KeyError) as exc:
#         logger.info(
#             "Batch embedding endpoint unavailable (%s); "
#             "falling back to per-chunk embedding calls.",
#             exc,
#         )

#     return [get_embedding(chunk) for chunk in texts]


def get_embedding(text_input: str) -> list[float]:
    """Get a single embedding vector from the configured embedding provider."""
    if settings.embedding_provider == "openai_compatible":
        response = _post_with_retry(
            f"{settings.embedding_api_base_url}/embeddings",
            json={"model": settings.embedding_api_model, "input": text_input},
            timeout=settings.ollama_request_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]

    # default: ollama
    response = _post_with_retry(
        f"{settings.ollama_base_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text_input},
        timeout=settings.ollama_request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple chunks, batching where the API allows it."""
    if not texts:
        return []

    if settings.embedding_provider == "openai_compatible":
        response = _post_with_retry(
            f"{settings.embedding_api_base_url}/embeddings",
            json={"model": settings.embedding_api_model, "input": texts},
            timeout=settings.ollama_request_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        if len(data) == len(texts):
            # OpenAI-style responses aren't guaranteed to preserve order;
            # sort by the "index" field to be safe.
            data.sort(key=lambda item: item["index"])
            return [item["embedding"] for item in data]
        logger.warning(
            "OpenAI-compatible embeddings endpoint returned unexpected shape; "
            "falling back to per-chunk calls."
        )
        return [get_embedding(chunk) for chunk in texts]

    # default: ollama (unchanged)
    try:
        response = _post_with_retry(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.ollama_embedding_model, "input": texts},
            timeout=settings.ollama_request_timeout_seconds,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings")
        if embeddings and len(embeddings) == len(texts):
            return embeddings
        logger.warning(
            "Batch embedding endpoint returned unexpected shape; "
            "falling back to per-chunk embedding calls."
        )
    except (httpx.HTTPStatusError, httpx.TransportError, KeyError) as exc:
        logger.info(
            "Batch embedding endpoint unavailable (%s); "
            "falling back to per-chunk embedding calls.",
            exc,
        )

    return [get_embedding(chunk) for chunk in texts]

# def generate_response(query: str, context: str) -> str:
#     """Generate a grounded answer from the LLM given retrieved context."""
#     prompt = f"""You are a helpful assistant. Answer concisely based ONLY on the context below.
# If the answer is not in the context, say "I don't have enough information to answer that."

# Context:
# {context}

# Question: {query}

# Answer in 2-3 sentences maximum:"""

#     response = _post_with_retry(
#         f"{settings.ollama_base_url}/api/generate",
#         json={
#             "model": settings.ollama_model,
#             "prompt": prompt,
#             "stream": False,
#             "options": {
#                 "num_predict": 200,
#                 "temperature": 0.1,
#                 "top_k": 10,
#                 "top_p": 0.5,
#             },
#         },
#         timeout=settings.ollama_generate_timeout_seconds,
#     )
#     response.raise_for_status()
#     return response.json()["response"]

def generate_response(query: str, context: str) -> str:
    """Generate a grounded answer from the LLM given retrieved context."""
    prompt = f"""You are a helpful assistant. Answer concisely based ONLY on the context below.
If the answer is not in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {query}

Answer in 2-3 sentences maximum:"""

    if settings.llm_provider == "openai_compatible":
        response = _post_with_retry(
            f"{settings.llm_api_base_url}/chat/completions",
            json={
                "model": settings.llm_api_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1,
                "top_p": 0.5,
            },
            timeout=settings.ollama_generate_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    # default: ollama (unchanged)
    response = _post_with_retry(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 200,
                "temperature": 0.1,
                "top_k": 10,
                "top_p": 0.5,
            },
        },
        timeout=settings.ollama_generate_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["response"]
# def check_ollama_connection() -> bool:
#     """Used by the /health endpoint. Cheap call, short timeout."""
#     try:
#         response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
#         return response.status_code == 200
#     except httpx.TransportError:
#         return False

def check_llm_connection() -> bool:
    """Used by the /health endpoint. Cheap call, short timeout."""
    if settings.llm_provider == "openai_compatible":
        try:
            response = httpx.get(
                f"{settings.llm_api_base_url}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                timeout=5.0,
            )
            return response.status_code == 200
        except httpx.TransportError:
            return False

    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
        return response.status_code == 200
    except httpx.TransportError:
        return False
    


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF's pages, concatenated."""
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = "".join(page.extract_text() or "" for page in reader.pages)
    if not full_text.strip():
        raise ValueError(
            "Could not extract any text from this PDF. It may be a scanned "
            "image without OCR, or password-protected."
        )
    return full_text


def find_existing_document(db: Session, content_hash: str) -> Document | None:
    """Look up a document by content hash."""
    return db.query(Document).filter(Document.content_hash == content_hash).first()


def create_document_record(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    db: Session,
) -> tuple[Document, bool]:
    """Validate an upload and create (or find) its Document row."""
    if not looks_like_pdf(file_bytes):
        raise ValueError("File does not appear to be a valid PDF (magic number mismatch).")

    content_hash = compute_file_hash(file_bytes)

    existing = find_existing_document(db, content_hash)
    if existing is not None:
        logger.info(
            "Duplicate upload detected for %r (content_hash=%s); "
            "returning existing document id=%d instead of re-ingesting.",
            filename,
            content_hash[:12],
            existing.id,
        )
        return existing, True

    doc = Document(
        filename=filename,
        content_type=content_type,
        content_hash=content_hash,
        file_size_bytes=len(file_bytes),
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        existing = find_existing_document(db, content_hash)
        if existing is not None:
            logger.info(
                "Lost a race to ingest %r; another request created document id=%d.",
                filename,
                existing.id,
            )
            return existing, True
        raise

    db.refresh(doc)
    return doc, False


def process_document(document_id: int, file_bytes: bytes) -> None:
    """Background task: extract text, chunk it, embed, and store."""
    from app.db.database import get_session  # local import avoids a cycle at module load

    db = get_session()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc is None:
            logger.error("process_document: document id=%d no longer exists", document_id)
            return

        doc.status = DocumentStatus.PROCESSING
        db.commit()

        full_text = extract_text_from_pdf(file_bytes)
        chunks = chunk_text(full_text)
        if not chunks:
            raise ValueError("Document produced no usable chunks after splitting.")

        embeddings = get_embeddings_batch(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk,
                    embedding=embedding,
                )
            )

        doc.status = DocumentStatus.COMPLETED
        doc.chunk_count = len(chunks)
        doc.error_message = None
        db.commit()
        logger.info("Ingestion completed for document id=%d (%d chunks)", doc.id, len(chunks))

    except Exception as exc:
        db.rollback()
        logger.exception("Ingestion failed for document id=%d", document_id)
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc is not None:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(exc)[:2000]
            db.commit()
    finally:
        db.close()


def delete_document(document_id: int, db: Session) -> bool:
    """Delete a document and its chunks (cascade). Returns False if not found."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        return False
    db.delete(doc)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Retrieval & generation
# ---------------------------------------------------------------------------


def query_rag(query: str, db: Session, top_k: int = settings.retrieval_top_k) -> dict:
    """Retrieve the most relevant chunks and generate a grounded answer."""
    query_embedding = get_embedding(query)

    results = db.execute(
        text(
            """
            SELECT
                dc.document_id,
                d.filename,
                dc.chunk_index,
                dc.content,
                1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.status = 'completed'
            ORDER BY dc.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        ),
        {"embedding": str(query_embedding), "top_k": top_k},
    ).fetchall()

    if not results:
        return {
            "answer": (
                "I don't have any indexed documents to search yet. "
                "Please upload a PDF and wait for it to finish processing."
            ),
            "sources": [],
        }

    context = "\n\n".join(row.content for row in results)
    sources = [
        {
            "document_id": row.document_id,
            "filename": row.filename,
            "chunk_index": row.chunk_index,
            "content": row.content[:200],
            "similarity": float(row.similarity),
        }
        for row in results
    ]
    answer = generate_response(query, context)
    return {"answer": answer, "sources": sources}