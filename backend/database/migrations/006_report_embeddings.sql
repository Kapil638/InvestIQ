-- InvestIQ: report embeddings for RAG (replaces local ChromaDB)
-- Run this in the Supabase SQL Editor (Dashboard -> SQL -> New query)
--
-- Why: ChromaDB persisted to local disk, which is ephemeral on Render's free
-- tier - CHROMA_ENABLED was set to false in production, silently disabling
-- "institutional memory" (what changed since the last report) entirely.
-- Supabase/Postgres is already the durable store this app depends on for
-- reports, so pgvector removes the local-disk dependency instead of working
-- around it.

CREATE EXTENSION IF NOT EXISTS vector;

-- 384 dims matches chromadb's DefaultEmbeddingFunction (all-MiniLM-L6-v2),
-- reused here as a pure embedding utility (no chromadb persistence layer).
CREATE TABLE IF NOT EXISTS report_embeddings (
    id UUID PRIMARY KEY,
    report_id UUID NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    rating VARCHAR(20),
    generated_at TIMESTAMPTZ NOT NULL,
    chunk_section VARCHAR(50),
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_embeddings_report_id
    ON report_embeddings (report_id);

CREATE INDEX IF NOT EXISTS idx_report_embeddings_ticker
    ON report_embeddings (ticker);

-- HNSW index for fast approximate cosine similarity search.
CREATE INDEX IF NOT EXISTS idx_report_embeddings_hnsw
    ON report_embeddings USING hnsw (embedding vector_cosine_ops);

-- PostgREST can't express vector distance operators directly, so similarity
-- search goes through this RPC function (called via supabase-py's .rpc()).
CREATE OR REPLACE FUNCTION match_report_embeddings(
    query_embedding vector(384),
    match_ticker VARCHAR DEFAULT NULL,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    report_id UUID,
    ticker VARCHAR,
    rating VARCHAR,
    generated_at TIMESTAMPTZ,
    content TEXT,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        report_embeddings.report_id,
        report_embeddings.ticker,
        report_embeddings.rating,
        report_embeddings.generated_at,
        report_embeddings.content,
        1 - (report_embeddings.embedding <=> query_embedding) AS similarity
    FROM report_embeddings
    WHERE match_ticker IS NULL OR report_embeddings.ticker = match_ticker
    ORDER BY report_embeddings.embedding <=> query_embedding
    LIMIT match_count;
$$;
