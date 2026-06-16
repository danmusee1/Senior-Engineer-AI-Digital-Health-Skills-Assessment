"""
Tests for RAG API endpoints (app/rag/routes.py).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# Import shared engine/session from conftest
from tests.conftest import TEST_ENGINE, TestingSessionLocal

from app.db.database import get_db
from app.db.models import Document, DocumentStatus
from app.rag.routes import router

# ---------------------------------------------------------------------------
# Minimal valid PDF bytes
# ---------------------------------------------------------------------------
VALID_PDF_BYTES = b"%PDF-1.4 fake-but-magic-number-is-correct"
INVALID_PDF_BYTES = b"this is not a pdf at all"
BIG_PDF_BYTES = VALID_PDF_BYTES + b"x" * (21 * 1024 * 1024)  # > 20 MB

PATCH_BASE = "app.rag.routes"
PDF_CONTENT_TYPE = "application/pdf"
API_KEY_HEADERS = {"x-api-key": "test-secret"}


# ---------------------------------------------------------------------------
# DB session fixture
# ---------------------------------------------------------------------------
@pytest.fixture()
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# FastAPI test app
# ---------------------------------------------------------------------------
def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _upload(
    client: TestClient,
    content: bytes = VALID_PDF_BYTES,
    filename: str = "test.pdf",
    content_type: str = PDF_CONTENT_TYPE,
):
    return client.post(
        "/rag/upload",
        files={"file": (filename, io.BytesIO(content), content_type)},
        headers=API_KEY_HEADERS,
    )


def _make_document(db: Session, **kwargs) -> Document:
    """Insert a Document row directly — bypasses the service layer."""
    defaults = dict(
        filename="sample.pdf",
        content_type="application/pdf",
        content_hash="abc123",
        file_size_bytes=1024,
        status=DocumentStatus.COMPLETED,
        chunk_count=3,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    if isinstance(defaults.get("status"), DocumentStatus):
        defaults["status"] = defaults["status"].value
    doc = Document(**defaults)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ===========================================================================
# POST /rag/upload
# ===========================================================================
class TestUpload:

    def test_rejects_non_pdf_content_type(self, client):
        resp = _upload(client, content_type="text/plain")
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]

    def test_rejects_oversized_file(self, client):
        with patch(f"{PATCH_BASE}.looks_like_pdf", return_value=True), \
             patch(f"{PATCH_BASE}.create_document_record"):
            resp = _upload(client, content=BIG_PDF_BYTES)
        assert resp.status_code == 400
        assert "large" in resp.json()["detail"].lower()

    def test_rejects_file_without_pdf_magic(self, client):
        resp = _upload(client, content=INVALID_PDF_BYTES)
        assert resp.status_code == 422

    def test_successful_new_upload_queues_background_task(self, client, db):
        doc = _make_document(db, status=DocumentStatus.PENDING)

        with patch(f"{PATCH_BASE}.looks_like_pdf", return_value=True), \
             patch(f"{PATCH_BASE}.create_document_record", return_value=(doc, False)), \
             patch(f"{PATCH_BASE}.process_document") as mock_process:
            resp = _upload(client)

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_duplicate"] is False
        assert body["document"]["id"] == doc.id
        mock_process.assert_called_once_with(doc.id, VALID_PDF_BYTES)

    def test_duplicate_upload_does_not_queue_task(self, client, db):
        doc = _make_document(db, status=DocumentStatus.COMPLETED)

        with patch(f"{PATCH_BASE}.looks_like_pdf", return_value=True), \
             patch(f"{PATCH_BASE}.create_document_record", return_value=(doc, True)), \
             patch(f"{PATCH_BASE}.process_document") as mock_process:
            resp = _upload(client)

        assert resp.status_code == 200
        assert resp.json()["is_duplicate"] is True
        mock_process.assert_not_called()

    def test_service_value_error_returns_422(self, client):
        with patch(f"{PATCH_BASE}.looks_like_pdf", return_value=True), \
             patch(f"{PATCH_BASE}.create_document_record", side_effect=ValueError("bad pdf")):
            resp = _upload(client)

        assert resp.status_code == 422
        assert "bad pdf" in resp.json()["detail"]


# ===========================================================================
# POST /rag/query
# ===========================================================================
class TestQuery:
    ENDPOINT = "/rag/query"

    def test_successful_query_returns_answer_and_sources(self, client):
        mock_result = {
            "answer": "The capital is Nairobi.",
            "sources": [
                {
                    "document_id": 1,
                    "filename": "geo.pdf",
                    "chunk_index": 0,
                    "content": "Kenya's capital is Nairobi.",
                    "similarity": 0.95,
                }
            ],
        }
        with patch(f"{PATCH_BASE}.query_rag", return_value=mock_result):
            resp = client.post(self.ENDPOINT, json={"query": "What is the capital of Kenya?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "The capital is Nairobi."
        assert len(body["sources"]) == 1
        assert body["sources"][0]["similarity"] == 0.95

    def test_query_uses_custom_top_k(self, client):
        with patch(f"{PATCH_BASE}.query_rag", return_value={"answer": "ok", "sources": []}) as mock_q:
            client.post(self.ENDPOINT, json={"query": "hello", "top_k": 7})
        args = mock_q.call_args
        top_k = args[1].get("top_k") if args[1] else args[0][2]
        assert top_k == 7

    def test_empty_query_string_is_rejected(self, client):
        resp = client.post(self.ENDPOINT, json={"query": ""})
        assert resp.status_code == 422

    def test_missing_query_field_is_rejected(self, client):
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_service_exception_returns_500(self, client):
        with patch(f"{PATCH_BASE}.query_rag", side_effect=RuntimeError("embedding service down")):
            resp = client.post(self.ENDPOINT, json={"query": "anything"})
        assert resp.status_code == 500
        assert "Query failed" in resp.json()["detail"]

    def test_no_documents_indexed_returns_graceful_answer(self, client):
        no_docs = {"answer": "I don't have any indexed documents.", "sources": []}
        with patch(f"{PATCH_BASE}.query_rag", return_value=no_docs):
            resp = client.post(self.ENDPOINT, json={"query": "anything"})
        assert resp.status_code == 200
        assert resp.json()["sources"] == []


# ===========================================================================
# GET /rag/documents
# ===========================================================================
class TestListDocuments:
    ENDPOINT = "/rag/documents"

    def test_empty_returns_empty_list(self, client):
        resp = client.get(self.ENDPOINT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_returns_all_documents(self, client, db):
        _make_document(db, filename="a.pdf", content_hash="h1")
        _make_document(db, filename="b.pdf", content_hash="h2")
        resp = client.get(self.ENDPOINT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_pagination_limit(self, client, db):
        for i in range(5):
            _make_document(db, filename=f"doc{i}.pdf", content_hash=f"hash{i}")
        resp = client.get(self.ENDPOINT, params={"limit": 2, "offset": 0})
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    def test_pagination_offset(self, client, db):
        for i in range(5):
            _make_document(db, filename=f"doc{i}.pdf", content_hash=f"hash{i}")
        resp = client.get(self.ENDPOINT, params={"limit": 10, "offset": 3})
        assert len(resp.json()["items"]) == 2

    def test_invalid_limit_rejected(self, client):
        assert client.get(self.ENDPOINT, params={"limit": 0}).status_code == 422
        assert client.get(self.ENDPOINT, params={"limit": 101}).status_code == 422

    def test_invalid_offset_rejected(self, client):
        assert client.get(self.ENDPOINT, params={"offset": -1}).status_code == 422

    def test_documents_ordered_newest_first(self, client, db):
        old = _make_document(
            db, filename="old.pdf", content_hash="h_old",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        new = _make_document(
            db, filename="new.pdf", content_hash="h_new",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        items = client.get(self.ENDPOINT).json()["items"]
        assert items[0]["id"] == new.id
        assert items[1]["id"] == old.id


# ===========================================================================
# GET /rag/documents/{document_id}
# ===========================================================================
class TestGetDocument:

    def test_returns_document_when_found(self, client, db):
        doc = _make_document(db)
        resp = client.get(f"/rag/documents/{doc.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == doc.id
        assert resp.json()["filename"] == doc.filename

    def test_returns_404_when_not_found(self, client):
        resp = client.get("/rag/documents/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_returns_correct_status_field(self, client, db):
        doc = _make_document(db, status=DocumentStatus.PROCESSING)
        resp = client.get(f"/rag/documents/{doc.id}")
        assert resp.json()["status"] == "processing"


# ===========================================================================
# DELETE /rag/documents/{document_id}
# ===========================================================================
class TestDeleteDocument:

    def test_successful_delete_returns_204(self, client, db):
        doc = _make_document(db)
        with patch(f"{PATCH_BASE}.delete_document", return_value=True):
            resp = client.delete(f"/rag/documents/{doc.id}", headers=API_KEY_HEADERS)
        assert resp.status_code == 204
        assert resp.content == b""

    def test_delete_nonexistent_returns_404(self, client):
        with patch(f"{PATCH_BASE}.delete_document", return_value=False):
            resp = client.delete("/rag/documents/99999", headers=API_KEY_HEADERS)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_actually_removes_from_db(self, client, db):
        doc = _make_document(db)
        doc_id = doc.id

        from app.rag.service import delete_document as real_delete
        with patch(f"{PATCH_BASE}.delete_document", wraps=real_delete):
            resp = client.delete(f"/rag/documents/{doc_id}", headers=API_KEY_HEADERS)

        assert resp.status_code == 204
        assert db.query(Document).filter(Document.id == doc_id).first() is None