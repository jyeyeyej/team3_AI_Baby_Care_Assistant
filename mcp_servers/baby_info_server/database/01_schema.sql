-- Owned by baby_info_server.  Apply once to the shared PostgreSQL database.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(100) PRIMARY KEY,
    title TEXT NOT NULL,
    organization TEXT NOT NULL,
    source_url TEXT NOT NULL,
    verified_at DATE,
    category VARCHAR(20) NOT NULL CHECK (category IN ('feeding', 'sleep', 'weaning', 'development', 'safety', 'stool')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(100) PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    age_min_months INTEGER CHECK (age_min_months IS NULL OR age_min_months BETWEEN 0 AND 36),
    age_max_months INTEGER CHECK (age_max_months IS NULL OR age_max_months BETWEEN 0 AND 36),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_document_chunks_index UNIQUE (document_id, chunk_index),
    CONSTRAINT ck_document_chunks_age_range CHECK (age_min_months IS NULL OR age_max_months IS NULL OR age_min_months <= age_max_months)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_cosine ON document_chunks USING hnsw (embedding vector_cosine_ops);
