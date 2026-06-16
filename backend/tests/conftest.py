"""
Shared pytest fixtures.
"""

import pytest
from sqlalchemy import create_engine, text, StaticPool
from sqlalchemy.orm import sessionmaker

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=TEST_ENGINE, autocommit=False, autoflush=False
)

_CREATE_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    filename         VARCHAR(255)  NOT NULL,
    content_type     VARCHAR(100)  NOT NULL,
    content_hash     VARCHAR(64)   NOT NULL UNIQUE,
    file_size_bytes  INTEGER       NOT NULL DEFAULT 0,
    status           VARCHAR(20)   NOT NULL DEFAULT 'pending',
    chunk_count      INTEGER       NOT NULL DEFAULT 0,
    error_message    TEXT,
    created_at       DATETIME,
    updated_at       DATETIME
)
"""

_CREATE_DOCUMENT_CHUNKS = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT    NOT NULL,
    embedding    TEXT,
    created_at   DATETIME
)
"""


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate both tables before every test."""
    with TEST_ENGINE.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("DROP TABLE IF EXISTS document_chunks"))
        conn.execute(text("DROP TABLE IF EXISTS documents"))
        conn.execute(text(_CREATE_DOCUMENTS))
        conn.execute(text(_CREATE_DOCUMENT_CHUNKS))
        conn.commit()
    yield