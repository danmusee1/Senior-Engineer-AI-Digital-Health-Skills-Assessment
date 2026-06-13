# Core RAG service — embedding, ingestion, retrieval, generation.

import os
import httpx
from pypdf import PdfReader
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import Document, DocumentChunk

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


# ---------- Helpers ----------

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if c]


def get_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama."""
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": OLLAMA_EMBEDDING_MODEL, "prompt": text},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def generate_response(query: str, context: str) -> str:
    """Generate RAG response from Ollama LLM."""
    prompt = f"""You are a helpful assistant. Answer the question based ONLY on the context provided below.
If the answer is not in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {query}

Answer:"""

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["response"]


# ---------- Core RAG functions ----------

def ingest_pdf(file_bytes: bytes, filename: str, db: Session) -> Document:
    """Parse PDF, chunk text, embed, and store in pgvector."""
    import io
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""

    if not full_text.strip():
        raise ValueError("Could not extract text from PDF.")

    # Save document record
    doc = Document(filename=filename, content_type="application/pdf")
    db.add(doc)
    db.flush()  # get doc.id without committing

    # Chunk, embed, store
    chunks = chunk_text(full_text)
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
        db.add(DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            content=chunk,
            embedding=embedding,
        ))

    db.commit()
    db.refresh(doc)
    return doc


def query_rag(query: str, db: Session, top_k: int = 5) -> dict:
    """Embed query, retrieve top-k chunks, generate response."""
    query_embedding = get_embedding(query)

    # pgvector cosine similarity search
    results = db.execute(
        text("""
            SELECT content, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM document_chunks
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        {"embedding": str(query_embedding), "top_k": top_k},
    ).fetchall()

    if not results:
        return {"answer": "No documents found. Please upload a PDF first.", "sources": []}

    context = "\n\n".join([row.content for row in results])
    sources = [{"content": row.content[:200], "similarity": float(row.similarity)} for row in results]

    answer = generate_response(query, context)
    return {"answer": answer, "sources": sources}
