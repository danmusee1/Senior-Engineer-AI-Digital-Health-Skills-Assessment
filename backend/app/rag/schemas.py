"""
Pydantic schemas for the RAG API.

Keeping these separate from the SQLAlchemy models (app/db/models.py) means
the API contract can evolve independently of the storage schema — e.g. we
can rename a database column without it being a breaking API change, and we
control exactly which fields (and validation rules) are exposed to clients.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models import DocumentStatus


class DocumentResponse(BaseModel):
    """A document, as returned by upload / list / detail endpoints."""

    id: int
    filename: str
    content_type: str
    file_size_bytes: int
    status: DocumentStatus
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    """Response returned immediately after an upload is accepted.

    Ingestion happens in the background, so `status` will typically be
    `pending` or `processing` here — poll GET /rag/documents/{id} (or use
    GET /rag/documents) to see when it becomes `completed`.
    """

    document: DocumentResponse
    is_duplicate: bool = Field(
        description=(
            "True if a document with identical content was already uploaded "
            "previously. In that case `document` is the *existing* record — "
            "no new ingestion was triggered, and no duplicate chunks were "
            "created."
        )
    )


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Natural-language question.")
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of chunks to retrieve as context for the answer.",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query cannot be empty or whitespace-only.")
        return stripped


class SourceChunk(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    content: str
    similarity: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class ErrorResponse(BaseModel):
    """Shape of every error response returned by this API.

    A consistent error shape (rather than ad-hoc dicts per endpoint) makes
    frontend error handling and automated tests simpler, and avoids
    accidentally leaking internal details (stack traces, file paths) in
    production — see app/main.py's exception handlers.
    """

    detail: str
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: bool
    ollama: bool