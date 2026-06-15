"""RAG API endpoints — upload, query, list, delete."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_api_key
from app.db.database import get_db
from app.db.models import Document
from app.rag.schemas import (
    DocumentListResponse,
    DocumentResponse,
    QueryRequest,
    QueryResponse,
    UploadResponse,
)
from app.rag.service import create_document_record, delete_document, looks_like_pdf, process_document, query_rag

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a PDF for ingestion",
    dependencies=[Depends(require_api_key)],
)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max {settings.max_upload_size_mb}MB.",
        )

    if not looks_like_pdf(file_bytes):
        raise HTTPException(status_code=422, detail="File does not appear to be a valid PDF.")

    try:
        doc, is_duplicate = create_document_record(file_bytes, file.filename, file.content_type, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not is_duplicate:
        background_tasks.add_task(process_document, doc.id, file_bytes)

    return UploadResponse(document=DocumentResponse.model_validate(doc), is_duplicate=is_duplicate)


@router.post("/query", response_model=QueryResponse, summary="Query the RAG system")
async def query(request: QueryRequest, db: Session = Depends(get_db)):
    try:
        return query_rag(request.query, db, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")


@router.get("/documents", response_model=DocumentListResponse, summary="List documents")
def list_documents(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    total = db.query(Document).count()
    items = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse, summary="Get a document")
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(doc)


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete a document and its chunks",
    dependencies=[Depends(require_api_key)],
)
def remove_document(document_id: int, db: Session = Depends(get_db)):
    if not delete_document(document_id, db):
        raise HTTPException(status_code=404, detail="Document not found.")