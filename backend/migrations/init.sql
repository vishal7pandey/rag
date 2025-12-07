-- Initial schema for RAG vector storage (Story 003)

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100),
    filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(50),
    total_chunks INTEGER DEFAULT 0,
    file_size BIGINT,
    ingestion_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks table (core data)
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,

    -- Content
    content TEXT NOT NULL,
    original_content TEXT,

    -- Embedding references (vectors in Pinecone)
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    embedding_generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Backup vector (pgvector)
    dense_embedding vector(1536),

    -- Metadata
    source VARCHAR(255),
    document_type VARCHAR(50),
    language VARCHAR(10) DEFAULT 'en',
    page_number INTEGER,
    section_title VARCHAR(255),
    user_id VARCHAR(100),

    -- Quality & Status
    quality_score DECIMAL(3, 2) DEFAULT 0.5 CHECK (quality_score >= 0 AND quality_score <= 1),
    is_duplicate BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint per document
    UNIQUE (document_id, chunk_index)
);

-- Chunk metadata (enriched data)
CREATE TABLE IF NOT EXISTS chunk_metadata (
    chunk_id UUID PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    entities JSONB,
    keywords JSONB,
    summary TEXT,
    category VARCHAR(100),
    tags JSONB
);

-- Retrieval logs (analytics)
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id SERIAL PRIMARY KEY,
    query_id UUID,
    user_id VARCHAR(100),
    query_text TEXT NOT NULL,
    search_type VARCHAR(20),
    retrieved_chunk_ids UUID[],
    top_k INTEGER,
    total_results INTEGER,
    latency_ms INTEGER,
    filters JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Evaluation feedback (quality scores)
CREATE TABLE IF NOT EXISTS evaluation_feedback (
    id SERIAL PRIMARY KEY,
    chunk_id UUID REFERENCES chunks(id),
    query_id UUID,
    faithfulness_score DECIMAL(3, 2),
    answer_relevancy_score DECIMAL(3, 2),
    context_recall_score DECIMAL(3, 2),
    context_precision_score DECIMAL(3, 2),
    overall_quality_score DECIMAL(3, 2),
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for documents and chunks
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (ingestion_status);

CREATE INDEX IF NOT EXISTS idx_document_id ON chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_quality_score ON chunks (quality_score);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON chunks (created_at);
CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON chunks (user_id);

-- Full-text search index on chunks.content
CREATE INDEX IF NOT EXISTS idx_content_gin
    ON chunks USING GIN (to_tsvector('english', content));

-- Indexes for retrieval_logs and evaluation_feedback
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_user_id ON retrieval_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_created_at ON retrieval_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_query_id ON retrieval_logs (query_id);

CREATE INDEX IF NOT EXISTS idx_feedback_chunk_id ON evaluation_feedback (chunk_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON evaluation_feedback (created_at);

-- Debug artifacts (Story 016)
CREATE TABLE IF NOT EXISTS debug_artifacts (
    id SERIAL PRIMARY KEY,
    trace_id VARCHAR(100) NOT NULL,
    artifact_type VARCHAR(50) NOT NULL,
    artifact_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_debug_artifacts_trace_id_created_at
    ON debug_artifacts (trace_id, created_at);

-- Trigger function for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic updated_at maintenance
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_documents_updated_at'
    ) THEN
        CREATE TRIGGER update_documents_updated_at
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_chunks_updated_at'
    ) THEN
        CREATE TRIGGER update_chunks_updated_at
            BEFORE UPDATE ON chunks
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;
