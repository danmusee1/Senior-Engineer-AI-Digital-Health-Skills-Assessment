#rag/routes.py
# RAG API endpoints — upload and chat.

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.rag.service import ingest_pdf, query_rag

router = APIRouter(prefix="/rag", tags=["RAG"])


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]


@router.post("/upload", summary="Upload a PDF for ingestion")
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    
    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 20MB.")

    try:
        doc = ingest_pdf(file_bytes, file.filename, db)
        return {"message": "PDF ingested successfully.", "document_id": doc.id, "filename": doc.filename}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/query", response_model=QueryResponse, summary="Query the RAG system")
async def query(request: QueryRequest, db: Session = Depends(get_db)):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    try:
        result = query_rag(request.query, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/documents", summary="List all ingested documents")
def list_documents(db: Session = Depends(get_db)):
    from app.db.models import Document
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [{"id": d.id, "filename": d.filename, "created_at": str(d.created_at)} for d in docs]
