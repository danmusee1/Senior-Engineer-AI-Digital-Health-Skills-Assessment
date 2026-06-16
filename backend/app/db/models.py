"""SQLAlchemy models for the RAG pipeline."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models import Base
from app.core.config import settings

# pgvector shim: use Vector on Postgres, fall back to Text for SQLite tests
try:
    from pgvector.sqlalchemy import Vector as _PgVector
    _VectorType = _PgVector(settings.ollama_embedding_dim)
except Exception:
    _VectorType = Text()


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    # String instead of Postgres Enum so SQLite works in tests
    status = Column(String(20), nullable=False, default=DocumentStatus.PENDING.value)
    chunk_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(_VectorType, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")