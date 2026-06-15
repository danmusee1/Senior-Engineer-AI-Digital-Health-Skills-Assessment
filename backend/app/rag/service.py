#rag/service.py
# Core RAG service — embedding, ingestion, retrieval, generation.
import os
import io
import httpx
from pypdf import PdfReader
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import Document, DocumentChunk

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if c]

def get_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": OLLAMA_EMBEDDING_MODEL, "prompt": text},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]

def generate_response(query: str, context: str) -> str:
    prompt = f"""You are a helpful assistant. Answer concisely based ONLY on the context below.
If the answer is not in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {query}

Answer in 2-3 sentences maximum:"""

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 200,
                "temperature": 0.1,
                "top_k": 10,
                "top_p": 0.5,
            }
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["response"]

def ingest_pdf(file_bytes: bytes, filename: str, db: Session) -> Document:
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""
    if not full_text.strip():
        raise ValueError("Could not extract text from PDF.")
    doc = Document(filename=filename, content_type="application/pdf")
    db.add(doc)
    db.flush()
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

def query_rag(query: str, db: Session, top_k: int = 3) -> dict:
    query_embedding = get_embedding(query)
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
