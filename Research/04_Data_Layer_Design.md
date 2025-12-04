# Data Layer Design - Production RAG System

## Executive Summary

The **Data Layer** is the central nervous system of your RAG pipeline. It receives standardized Chunk objects from Ingestion and serves them at sub-100ms latency to Retrieval queries. It operates as a **hybrid storage + retrieval architecture**:

- **Pinecone (Managed Vector DB)**: Dense embeddings (semantic search), sparse embeddings (keyword search), metadata filtering
- **PostgreSQL + pgvector**: Optional metadata store, full-text backup search, audit trail
- **Redis Cache**: Query result caching, embedding cache for hot documents
- **Event Stream**: Async updates, consistency guarantees

This design treats the Data Layer as a **LEGO brick** that:
✓ Accepts perfectly-formed Chunk objects from Ingestion
✓ Serves them to Retrieval with <100ms latency
✓ Supports both dense + sparse (hybrid) search
✓ Enables metadata filtering, multi-tenancy, access control
✓ Provides observability hooks for monitoring
✓ Accepts feedback signals from Evaluation for re-indexing

---

## Part 1: Architecture Overview

### Data Layer as a LEGO Brick

```
┌──────────────────────────────────────────────────────────────────┐
│                    DATA LAYER (Hybrid Storage)                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  INPUT: Chunk Objects from Ingestion Pipeline                    │
│  ├─ id, content, dense_embedding (1536 dims)                    │
│  ├─ sparse_embedding (BM25 scores)                              │
│  ├─ metadata: {source, page_number, language, custom...}        │
│  ├─ quality_score, created_at, document_id                      │
│  └─ user_id, tenant_id (for multi-tenancy)                      │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │         PINECONE (Managed Vector Database)                 │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │ Dense Index (Semantic Search)                        │  │  │
│  │  │ ├─ Vectors: 1536 dimensions (text-embedding-3-small)│  │  │
│  │  │ ├─ Distance: Cosine similarity                       │  │  │
│  │  │ ├─ Indexing: HNSW (Hierarchical Navigable Small World)
│  │  │ ├─ HNSW Params: M=16, ef_construction=200            │  │  │
│  │  │ └─ Metadata: source, page_number, language, etc.     │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │                                                               │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │ Sparse Index (Keyword Search)                        │  │  │
│  │  │ ├─ Vectors: BM25 term weights                        │  │  │
│  │  │ ├─ Retrieval: Term-frequency based                   │  │  │
│  │  │ ├─ Language: English (configurable per chunk)        │  │  │
│  │  │ └─ Metadata: Same as dense index                     │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │                                                               │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │ Metadata Filtering                                   │  │  │
│  │  │ ├─ Equality: source = "resume.pdf"                  │  │  │
│  │  │ ├─ Range: page_number ≥ 5 AND page_number ≤ 10     │  │  │
│  │  │ ├─ Membership: language IN ["en", "fr"]             │  │  │
│  │  │ └─ Composite: (source="file1" OR source="file2")    │  │  │
│  │  │    AND language="en"                                │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │    PostgreSQL + pgvector (Metadata + Audit)              │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  ├─ chunks table: Full chunk records (for citations)     │  │
│  │  ├─ chunk_metadata table: Extracted entities, keywords   │  │
│  │  ├─ retrieval_logs table: Query logs for analysis        │  │
│  │  ├─ evaluation_feedback table: Quality scores per chunk  │  │
│  │  └─ Full-text index: For backup keyword search           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │    Redis Cache (Hot Data)                                 │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  ├─ query_results:{query_hash} → cached top-k chunks     │  │
│  │  ├─ hot_chunks:{chunk_id} → frequently accessed chunks   │  │
│  │  ├─ embedding_cache:{text_hash} → precomputed embeddings │  │
│  │  └─ TTL: 1-7 days (configurable per use case)            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  OUTPUT: Retrieved Chunks to Reranking/Generation               │
│  ├─ top_k chunks (typically 10-50)                              │
│  ├─ Sorted by relevance score (combined dense+sparse)           │
│  ├─ With metadata preserved (for attribution)                   │
│  └─ Search latency: <100ms (target)                             │
│                                                                    │
│  FEEDBACK LOOP: Evaluation → Quality Scores → Re-indexing        │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Component Specifications

### 2.1 Pinecone Dense Index Configuration

```python
"""
Dense Index: Semantic Search
- Embedding Model: text-embedding-3-small (OpenAI)
- Dimensions: 1536
- Distance Metric: Cosine similarity
- Indexing Algorithm: HNSW
"""

# Pinecone Index Configuration
DENSE_INDEX_CONFIG = {
    "name": "rag-dense",
    "dimension": 1536,  # text-embedding-3-small dimension
    "metric": "cosine",  # or "dotproduct", "euclidean"
    "spec": {
        "serverless": {
            "cloud": "aws",
            "region": "us-east-1"
        }
    },
    "metadata_config": {
        "indexed": [
            "source",  # For fast filtering by document
            "language",  # For language-specific retrieval
            "page_number",  # For page-level filtering
            "created_at",  # For freshness queries
            "chunk_index",  # For ordering within document
            "document_id",  # For document-level operations
            "user_id",  # For multi-tenancy
            "quality_score"  # For confidence-based filtering
        ]
    }
}

# Upsert dense vectors
def upsert_dense_vectors(chunks: List[Chunk]):
    """
    Store dense embeddings in Pinecone
    
    CONTRACT:
    - Input: List[Chunk] with dense_embedding, metadata
    - Output: Confirmed upsert (vectors available for search)
    - Time: ~500ms for 100 chunks
    """
    from pinecone import Pinecone
    
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("rag-dense")
    
    vectors_to_upsert = []
    
    for chunk in chunks:
        vector_record = (
            str(chunk.id),  # ID
            chunk.dense_embedding,  # 1536-dim vector
            {  # Metadata (filterable)
                "content": chunk.content,
                "source": chunk.metadata.get("source"),
                "page_number": chunk.metadata.get("page_number", 0),
                "language": chunk.metadata.get("language", "en"),
                "created_at": int(chunk.metadata.get("created_at", datetime.utcnow()).timestamp()),
                "chunk_index": chunk.chunk_index,
                "document_id": str(chunk.document_id),
                "user_id": chunk.metadata.get("user_id", "default"),
                "quality_score": chunk.quality_score or 0.5
            }
        )
        vectors_to_upsert.append(vector_record)
    
    # Batch upsert (efficient)
    index.upsert(vectors=vectors_to_upsert, namespace="default")
    
    logger.info(f"Upserted {len(vectors_to_upsert)} dense vectors")

# Query dense vectors
def query_dense(query_embedding: List[float], top_k: int = 10, 
                filters: Dict = None) -> List[Chunk]:
    """
    Semantic search using dense vectors
    
    CONTRACT:
    - Input: query_embedding (1536 dims), top_k, optional filters
    - Output: Ranked list of chunks
    - Time: <50ms for typical queries
    """
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("rag-dense")
    
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        filter=filters,  # Metadata filter expression
        include_metadata=True
    )
    
    # Convert to Chunk objects
    retrieved_chunks = []
    for match in results.matches:
        chunk = Chunk(
            id=UUID(match.id),
            content=match.metadata.get("content"),
            dense_embedding=query_embedding,  # Placeholder
            similarity_score=match.score,  # Cosine similarity
            retrieval_method="dense",
            rank=len(retrieved_chunks)
        )
        retrieved_chunks.append(chunk)
    
    return retrieved_chunks
```

### 2.2 Pinecone Sparse Index Configuration

```python
"""
Sparse Index: Keyword/Lexical Search using BM25
- Embedding Model: BM25 term-frequency weights
- Retrieval: Sparse vector similarity
- Use Case: Exact keyword matching, phrase search
"""

# Sparse Index Configuration
SPARSE_INDEX_CONFIG = {
    "name": "rag-sparse",
    "dimension": None,  # Dynamic (determined by vocabulary)
    "metric": "dotproduct",  # For sparse vectors
    "spec": {
        "serverless": {
            "cloud": "aws",
            "region": "us-east-1"
        }
    }
}

# Upsert sparse vectors
def upsert_sparse_vectors(chunks: List[Chunk]):
    """
    Store BM25 sparse embeddings in Pinecone
    
    CONTRACT:
    - Input: List[Chunk] with sparse_embedding (Dict[term, score])
    - Output: Confirmed upsert
    - Time: ~200ms for 100 chunks
    """
    from pinecone import Pinecone
    from pinecone.core.utils.namespaced_client import NamespacedClient
    
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("rag-sparse")
    
    vectors_to_upsert = []
    
    for chunk in chunks:
        # Convert sparse_embedding Dict to Pinecone format
        sparse_values = {
            "indices": list(chunk.sparse_embedding.keys()),  # Term IDs (as strings)
            "values": list(chunk.sparse_embedding.values())  # Term weights
        }
        
        vector_record = (
            str(chunk.id),
            [],  # Empty dense component (sparse-only)
            sparse_values,  # BM25 weights
            {  # Same metadata as dense
                "content": chunk.content,
                "source": chunk.metadata.get("source"),
                "page_number": chunk.metadata.get("page_number", 0),
                "language": chunk.metadata.get("language", "en"),
                "document_id": str(chunk.document_id)
            }
        )
        vectors_to_upsert.append(vector_record)
    
    # Batch upsert
    index.upsert(vectors=vectors_to_upsert, namespace="default")
    
    logger.info(f"Upserted {len(vectors_to_upsert)} sparse vectors")

# Query sparse vectors
def query_sparse(query_text: str, top_k: int = 10, 
                 filters: Dict = None) -> List[Chunk]:
    """
    Keyword search using sparse vectors
    
    CONTRACT:
    - Input: query_text (raw string), top_k, filters
    - Output: Ranked chunks by BM25 score
    - Time: <30ms
    """
    from rank_bm25 import BM25Okapi
    
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("rag-sparse")
    
    # Tokenize query (same tokenization as ingestion)
    query_tokens = query_text.lower().split()
    
    # Convert to BM25 sparse vector
    bm25 = BM25Okapi([query_tokens])  # Placeholder corpus
    query_sparse_vector = {
        "indices": query_tokens,
        "values": bm25.get_scores([query_tokens])[0].tolist()
    }
    
    results = index.query(
        sparse_vector=query_sparse_vector,
        top_k=top_k,
        filter=filters,
        include_metadata=True
    )
    
    retrieved_chunks = []
    for match in results.matches:
        chunk = Chunk(
            id=UUID(match.id),
            content=match.metadata.get("content"),
            bm25_score=match.score,  # BM25 score
            retrieval_method="sparse",
            rank=len(retrieved_chunks)
        )
        retrieved_chunks.append(chunk)
    
    return retrieved_chunks
```

### 2.3 Hybrid Search (Dense + Sparse Fusion)

```python
"""
Hybrid Search: Combine semantic + keyword retrieval
Strategy: Reciprocal Rank Fusion (RRF) to merge result sets
"""

def hybrid_search(
    query_text: str,
    query_embedding: List[float],
    top_k: int = 20,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    filters: Dict = None,
    search_mode: str = "rrf"  # "rrf", "weighted_sum", "interleave"
) -> List[Chunk]:
    """
    Hybrid search combining dense (semantic) + sparse (keyword)
    
    CONTRACT:
    - Input: query_text, query_embedding, weights, filters
    - Output: Fused top-k chunks
    - Time: <100ms (parallel queries + fusion)
    
    FUSION STRATEGIES:
    1. RRF (Reciprocal Rank Fusion): Recommended for balanced results
       score = 1/(rank_dense + 60) + 1/(rank_sparse + 60)
    2. Weighted Sum: Direct score combination with weights
       score = 0.6 * dense_score + 0.4 * sparse_score
    3. Interleave: Alternate results for diversity
    """
    
    import asyncio
    
    # Parallel queries
    async def fetch_results():
        dense_task = asyncio.create_task(
            query_dense_async(query_embedding, top_k=50, filters=filters)
        )
        sparse_task = asyncio.create_task(
            query_sparse_async(query_text, top_k=50, filters=filters)
        )
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
        return dense_results, sparse_results
    
    dense_results, sparse_results = asyncio.run(fetch_results())
    
    # Fusion
    if search_mode == "rrf":
        # Create rank dictionaries
        dense_ranks = {chunk.id: i for i, chunk in enumerate(dense_results)}
        sparse_ranks = {chunk.id: i for i, chunk in enumerate(sparse_results)}
        
        # Calculate RRF scores
        all_ids = set(dense_ranks.keys()) | set(sparse_ranks.keys())
        fused_scores = {}
        
        for chunk_id in all_ids:
            dense_rank = dense_ranks.get(chunk_id, len(dense_results) + 100)
            sparse_rank = sparse_ranks.get(chunk_id, len(sparse_results) + 100)
            
            # RRF formula (lower rank = higher score)
            rrf_score = 1.0 / (dense_rank + 60) + 1.0 / (sparse_rank + 60)
            fused_scores[chunk_id] = rrf_score
        
        # Sort by fused score
        sorted_ids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top-k chunks (fetch from combined results)
        chunk_map = {c.id: c for c in dense_results + sparse_results}
        fused_results = [chunk_map[cid] for cid, _ in sorted_ids[:top_k]]
        
    elif search_mode == "weighted_sum":
        # Normalize scores to 0-1 range
        dense_max = max([c.similarity_score for c in dense_results] or [1])
        sparse_max = max([c.bm25_score for c in sparse_results] or [1])
        
        # Create score dictionary
        all_chunks = {}
        for chunk in dense_results:
            norm_score = chunk.similarity_score / dense_max
            all_chunks[chunk.id] = {
                "chunk": chunk,
                "score": dense_weight * norm_score
            }
        
        for chunk in sparse_results:
            norm_score = chunk.bm25_score / sparse_max
            if chunk.id in all_chunks:
                all_chunks[chunk.id]["score"] += sparse_weight * norm_score
            else:
                all_chunks[chunk.id] = {
                    "chunk": chunk,
                    "score": sparse_weight * norm_score
                }
        
        # Sort and return
        fused_results = [
            v["chunk"] for v in sorted(
                all_chunks.values(),
                key=lambda x: x["score"],
                reverse=True
            )[:top_k]
        ]
    
    return fused_results
```

### 2.4 Metadata Filtering

```python
"""
Metadata Filtering: Precise retrieval with constraints
Examples:
- Only documents from Jan 2025
- Only PDF files from specific user
- Exclude documents with quality_score < 0.7
"""

def build_filter_expression(
    source: str = None,
    page_number_range: tuple = None,
    language: str = None,
    user_id: str = None,
    quality_threshold: float = None,
    created_after: datetime = None,
    created_before: datetime = None,
    document_ids: List[str] = None
) -> Dict:
    """
    Build Pinecone metadata filter expression
    
    CONTRACT:
    - Input: Multiple filter constraints
    - Output: Filter Dict compatible with Pinecone
    - Time: <1ms (just builds expression)
    
    EXAMPLE FILTERS:
    {"source": {"$eq": "resume.pdf"}}
    {"page_number": {"$gte": 5, "$lte": 10}}
    {"language": {"$in": ["en", "fr"]}}
    {"$and": [
        {"source": {"$eq": "report.pdf"}},
        {"quality_score": {"$gte": 0.8}}
    ]}
    """
    
    filters = []
    
    if source:
        filters.append({"source": {"$eq": source}})
    
    if language:
        filters.append({"language": {"$eq": language}})
    
    if user_id:
        filters.append({"user_id": {"$eq": user_id}})
    
    if page_number_range:
        min_page, max_page = page_number_range
        filters.append({
            "page_number": {"$gte": min_page, "$lte": max_page}
        })
    
    if quality_threshold is not None:
        filters.append({
            "quality_score": {"$gte": quality_threshold}
        })
    
    if created_after:
        filters.append({
            "created_at": {"$gte": int(created_after.timestamp())}
        })
    
    if created_before:
        filters.append({
            "created_at": {"$lte": int(created_before.timestamp())}
        })
    
    if document_ids:
        filters.append({
            "document_id": {"$in": document_ids}
        })
    
    # Combine with AND if multiple filters
    if len(filters) == 0:
        return None
    elif len(filters) == 1:
        return filters[0]
    else:
        return {"$and": filters}
```

---

## Part 3: PostgreSQL Metadata Store

### 3.1 Database Schema

```sql
-- Chunks table: Full content (for citations, auditing)
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    original_content TEXT,
    
    -- Embeddings
    dense_embedding_id UUID REFERENCES dense_embeddings(id),
    sparse_embedding_id UUID REFERENCES sparse_embeddings(id),
    embedding_model VARCHAR(100),
    embedding_generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    source VARCHAR(255),
    document_type VARCHAR(50),  -- pdf, txt, docx
    language VARCHAR(10),  -- en, fr, etc.
    page_number INTEGER,
    section_title VARCHAR(255),
    user_id VARCHAR(100),
    
    -- Quality & Status
    quality_score DECIMAL(3,2),  -- 0.0-1.0
    is_duplicate BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps & Tracing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ingestion_batch_id UUID,
    retrieval_rank INTEGER,
    
    -- Relationships
    FOREIGN KEY (document_id) REFERENCES documents(id),
    INDEX idx_document_id (document_id),
    INDEX idx_quality_score (quality_score),
    INDEX idx_created_at (created_at),
    FULLTEXT INDEX idx_content (content)  -- For FTS
);

-- Metadata store: Extracted entities, keywords, etc.
CREATE TABLE chunk_metadata (
    chunk_id UUID PRIMARY KEY,
    entities JSON,  -- [{"type": "PERSON", "value": "John"}, ...]
    keywords JSON,  -- ["keyword1", "keyword2", ...]
    summary TEXT,
    category VARCHAR(100),
    tags JSON,  -- ["urgent", "financial", ...]
    FOREIGN KEY (chunk_id) REFERENCES chunks(id)
);

-- Retrieval logs: For analytics, debugging
CREATE TABLE retrieval_logs (
    id SERIAL PRIMARY KEY,
    query_id UUID,
    user_id VARCHAR(100),
    query_text TEXT,
    search_type VARCHAR(20),  -- dense, sparse, hybrid
    retrieved_chunk_ids UUID[],
    top_k INTEGER,
    total_results INTEGER,
    latency_ms INTEGER,
    filters JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);

-- Evaluation feedback: Quality scores from evaluation component
CREATE TABLE evaluation_feedback (
    id SERIAL PRIMARY KEY,
    chunk_id UUID,
    query_id UUID,
    faithfulness_score DECIMAL(3,2),
    answer_relevancy_score DECIMAL(3,2),
    context_recall_score DECIMAL(3,2),
    context_precision_score DECIMAL(3,2),
    overall_quality_score DECIMAL(3,2),
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id),
    INDEX idx_chunk_id (chunk_id),
    INDEX idx_created_at (created_at)
);

-- Dense embeddings (optional, for caching)
CREATE TABLE dense_embeddings (
    id UUID PRIMARY KEY,
    embedding VECTOR(1536),  -- pgvector extension
    embedding_model VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_embedding ON dense_embeddings USING ivfflat (embedding vector_cosine_ops)
);

-- Sparse embeddings (optional, for caching)
CREATE TABLE sparse_embeddings (
    id UUID PRIMARY KEY,
    term_weights JSONB,  -- {"term1": 2.5, "term2": 1.2}
    language VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents table: Parent documents (for batch operations)
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    user_id VARCHAR(100),
    filename VARCHAR(255),
    document_type VARCHAR(50),
    total_chunks INTEGER,
    file_size BIGINT,
    ingestion_status VARCHAR(20),  -- success, partial, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);
```

### 3.2 PostgreSQL Operations

```python
"""
PostgreSQL integration for metadata + audit trail
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://user:password@localhost/rag_db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# ORM Models
Base = declarative_base()

class ChunkModel(Base):
    __tablename__ = "chunks"
    
    id = Column(String, primary_key=True)
    document_id = Column(String)
    content = Column(String)
    source = Column(String)
    quality_score = Column(float)
    created_at = Column(DateTime, default=datetime.utcnow)

class RetrievalLogModel(Base):
    __tablename__ = "retrieval_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    query_text = Column(String)
    retrieved_chunk_ids = Column(JSON)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

# Store chunks in PostgreSQL
def store_chunks_in_postgres(chunks: List[Chunk]):
    """
    Persist chunks to PostgreSQL for audit/retrieval
    
    CONTRACT:
    - Input: List[Chunk]
    - Output: Confirmed storage
    - Time: ~200ms for 50 chunks
    """
    session = Session()
    
    try:
        for chunk in chunks:
            chunk_record = ChunkModel(
                id=str(chunk.id),
                document_id=str(chunk.document_id),
                content=chunk.content,
                source=chunk.metadata.get("source"),
                quality_score=chunk.quality_score,
                created_at=chunk.metadata.get("created_at", datetime.utcnow())
            )
            session.add(chunk_record)
        
        session.commit()
        logger.info(f"Stored {len(chunks)} chunks in PostgreSQL")
        
    except Exception as e:
        logger.error(f"PostgreSQL storage error: {e}")
        session.rollback()
    finally:
        session.close()

# Log retrieval queries
def log_retrieval_query(
    user_id: str,
    query_text: str,
    retrieved_chunk_ids: List[str],
    latency_ms: int,
    search_type: str = "hybrid"
):
    """
    Log every retrieval query for analytics
    
    CONTRACT:
    - Input: Query metadata
    - Output: Logged to DB
    - Time: <10ms
    """
    session = Session()
    
    try:
        log_record = RetrievalLogModel(
            user_id=user_id,
            query_text=query_text,
            retrieved_chunk_ids=retrieved_chunk_ids,
            latency_ms=latency_ms
        )
        session.add(log_record)
        session.commit()
    except Exception as e:
        logger.warning(f"Failed to log retrieval: {e}")
    finally:
        session.close()
```

---

## Part 4: Redis Cache Layer

```python
"""
Redis cache for hot data + query result caching
Reduces latency for repeated queries, popular chunks
"""

import redis
import json
import hashlib
from typing import Optional

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379,
    db=0,
    decode_responses=True
)

class CacheManager:
    """Redis cache for chunks and query results"""
    
    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days default
    
    @staticmethod
    def cache_query_result(
        query_hash: str,
        results: List[Chunk],
        ttl_seconds: int = CACHE_TTL_SECONDS
    ):
        """
        Cache query results for quick retrieval
        
        Key: query:{hash}
        Value: JSON list of chunk IDs + scores
        TTL: Configurable (default 7 days)
        """
        cache_key = f"query:{query_hash}"
        cache_value = json.dumps([
            {
                "chunk_id": str(chunk.id),
                "similarity_score": chunk.similarity_score,
                "rank": chunk.rank
            }
            for chunk in results
        ])
        
        redis_client.setex(cache_key, ttl_seconds, cache_value)
        logger.info(f"Cached query result: {cache_key}")
    
    @staticmethod
    def get_cached_query_result(query_hash: str) -> Optional[List[Dict]]:
        """Retrieve cached query result"""
        cache_key = f"query:{query_hash}"
        cached = redis_client.get(cache_key)
        return json.loads(cached) if cached else None
    
    @staticmethod
    def cache_hot_chunk(chunk: Chunk, ttl_seconds: int = CACHE_TTL_SECONDS):
        """
        Cache frequently accessed chunks
        
        Key: chunk:{id}
        Value: Full chunk JSON (for quick access)
        """
        cache_key = f"chunk:{chunk.id}"
        cache_value = json.dumps({
            "id": str(chunk.id),
            "content": chunk.content,
            "metadata": chunk.metadata,
            "quality_score": chunk.quality_score
        })
        
        redis_client.setex(cache_key, ttl_seconds, cache_value)
    
    @staticmethod
    def get_cached_chunk(chunk_id: str) -> Optional[Dict]:
        """Retrieve cached chunk"""
        cache_key = f"chunk:{chunk_id}"
        cached = redis_client.get(cache_key)
        return json.loads(cached) if cached else None
    
    @staticmethod
    def cache_embedding(text_hash: str, embedding: List[float]):
        """
        Cache computed embeddings to avoid re-embedding
        
        Key: embedding:{hash}
        Value: JSON array of floats
        """
        cache_key = f"embedding:{text_hash}"
        cache_value = json.dumps(embedding)
        redis_client.setex(cache_key, 7 * 24 * 60 * 60, cache_value)
    
    @staticmethod
    def get_cached_embedding(text_hash: str) -> Optional[List[float]]:
        """Retrieve cached embedding"""
        cache_key = f"embedding:{text_hash}"
        cached = redis_client.get(cache_key)
        return json.loads(cached) if cached else None
    
    @staticmethod
    def invalidate_chunk_cache(chunk_id: str):
        """Invalidate cache when chunk is updated"""
        redis_client.delete(f"chunk:{chunk_id}")
    
    @staticmethod
    def get_cache_stats() -> Dict:
        """Get cache statistics"""
        info = redis_client.info()
        return {
            "used_memory_mb": info["used_memory"] / (1024 * 1024),
            "total_keys": redis_client.dbsize(),
            "hit_rate": info.get("keyspace_hits", 0)
        }
```

---

## Part 5: Data Layer API (Interface Contract)

```python
"""
Data Layer API: Interface between Ingestion and Retrieval
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class RetrievalRequest:
    """
    INPUT: What Retrieval asks Data Layer
    """
    query_id: str
    query_text: str
    query_embedding: List[float]
    top_k: int = 10
    search_type: str = "hybrid"  # dense, sparse, hybrid
    filters: Optional[Dict] = None
    include_metadata: bool = True
    user_id: Optional[str] = None
    timeout_ms: int = 5000

@dataclass
class RetrievedChunk:
    """
    OUTPUT: What Data Layer returns
    """
    chunk_id: str
    content: str
    metadata: Dict
    similarity_score: Optional[float] = None  # For dense
    bm25_score: Optional[float] = None  # For sparse
    fused_score: Optional[float] = None  # For hybrid
    rank: int
    retrieval_method: str  # dense, sparse, hybrid

class DataLayerService:
    """
    Main interface for Retrieval component to query Data Layer
    """
    
    async def retrieve(self, request: RetrievalRequest) -> List[RetrievedChunk]:
        """
        Main retrieval method
        
        CONTRACT:
        - Input: RetrievalRequest with query, embeddings, filters
        - Output: Top-k RetrievedChunks sorted by relevance
        - Time: <100ms
        """
        
        # Try cache first
        query_hash = hashlib.sha256(request.query_text.encode()).hexdigest()
        cached_results = CacheManager.get_cached_query_result(query_hash)
        
        if cached_results and not request.filters:  # Skip cache if filters present
            logger.info(f"Cache hit for query: {query_hash}")
            return cached_results
        
        # Execute retrieval
        start_time = time.time()
        
        if request.search_type == "dense":
            results = await self.query_dense(request)
        elif request.search_type == "sparse":
            results = await self.query_sparse(request)
        else:  # hybrid (default)
            results = await self.query_hybrid(request)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Cache results
        CacheManager.cache_query_result(query_hash, results)
        
        # Log to PostgreSQL
        await log_retrieval_query(
            user_id=request.user_id or "anonymous",
            query_text=request.query_text,
            retrieved_chunk_ids=[r.chunk_id for r in results],
            latency_ms=int(latency_ms),
            search_type=request.search_type
        )
        
        logger.info(
            f"Retrieval complete: {len(results)} chunks in {latency_ms:.1f}ms "
            f"({request.search_type})"
        )
        
        return results
    
    async def query_dense(self, request: RetrievalRequest) -> List[RetrievedChunk]:
        """Dense vector search"""
        # Implementation using query_dense_async from Part 2
        pass
    
    async def query_sparse(self, request: RetrievalRequest) -> List[RetrievedChunk]:
        """Sparse/keyword search"""
        # Implementation using query_sparse_async
        pass
    
    async def query_hybrid(self, request: RetrievalRequest) -> List[RetrievedChunk]:
        """Hybrid search with fusion"""
        # Implementation using hybrid_search
        pass
    
    async def upsert_chunks(self, chunks: List[Chunk]):
        """
        Called by Ingestion when new chunks are ready
        
        CONTRACT:
        - Input: List[Chunk] from ingestion pipeline
        - Output: Confirmed storage in all layers
        - Time: ~500ms for 100 chunks
        """
        
        # Parallel upsert to all storage layers
        tasks = [
            asyncio.create_task(self.upsert_to_pinecone_dense(chunks)),
            asyncio.create_task(self.upsert_to_pinecone_sparse(chunks)),
            asyncio.create_task(self.upsert_to_postgresql(chunks)),
            asyncio.create_task(self.warm_cache_hot_chunks(chunks))
        ]
        
        results = await asyncio.gather(*tasks)
        logger.info(f"Upserted {len(chunks)} chunks to all layers")
```

---

## Part 6: Monitoring & Observability

```python
"""
Data Layer Observability: Metrics, Traces, Alerts
"""

class DataLayerMetrics:
    """Track health and performance"""
    
    # Query metrics
    query_latency_ms = []
    queries_per_minute = 0
    cache_hit_rate = 0.0
    
    # Storage metrics
    total_chunks_indexed = 0
    index_size_gb = 0.0
    avg_chunk_density = 0.0
    
    # Error metrics
    query_errors = 0
    upsert_errors = 0
    
    @staticmethod
    def report_query_latency(latency_ms: float):
        """Report query execution time"""
        DataLayerMetrics.query_latency_ms.append(latency_ms)
        avg_latency = sum(DataLayerMetrics.query_latency_ms[-100:]) / 100
        
        if avg_latency > 200:  # Alert if > 200ms
            logger.warning(f"High query latency: {avg_latency}ms")
    
    @staticmethod
    def get_health_status() -> Dict:
        """Return current data layer health"""
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        dense_index = pc.Index("rag-dense")
        stats = dense_index.describe_index_stats()
        
        return {
            "status": "healthy",
            "total_vectors": stats.total_vector_count,
            "avg_query_latency_ms": statistics.mean(
                DataLayerMetrics.query_latency_ms[-100:]
            ) if DataLayerMetrics.query_latency_ms else 0,
            "cache_hit_rate": DataLayerMetrics.cache_hit_rate,
            "errors_last_hour": DataLayerMetrics.query_errors,
            "disk_usage_gb": stats.index_fullness * 100  # Percentage
        }
```

---

## Part 7: Integration Points (LEGO Fitting)

### 7.1 Ingestion → Data Layer

```python
# After ingestion completes, chunks flow to Data Layer
final_ingestion_result: IngestionResult = await ingestion_graph.ainvoke(state)

# Data Layer receives standardized Chunk objects
await data_layer.upsert_chunks(final_ingestion_result.chunks_created)

# Confirmation
logger.info(f"✓ {len(final_ingestion_result.chunks_created)} chunks indexed")
```

### 7.2 Data Layer → Retrieval

```python
# Retrieval submits query to Data Layer
retrieval_request = RetrievalRequest(
    query_id="q-123",
    query_text="What is X?",
    query_embedding=embeddings.embed_query("What is X?"),
    top_k=10,
    search_type="hybrid",
    filters={"user_id": "user-456"}
)

# Data Layer returns retrieved chunks
retrieved_chunks = await data_layer.retrieve(retrieval_request)

# Retrieval passes to Reranking
```

### 7.3 Evaluation → Data Layer (Feedback Loop)

```python
# After evaluation, quality scores update chunks
evaluation_feedback: List[EvaluationFeedback] = [
    EvaluationFeedback(
        chunk_id="chunk-123",
        quality_score=0.95,
        why_low=None
    ),
    ...
]

# Update quality scores in Data Layer
await data_layer.update_chunk_quality_scores(evaluation_feedback)

# Next retrieval uses these scores for confidence weighting
```

---

## Part 8: Configuration

```yaml
# data_layer_config.yaml
data_layer:
  # Pinecone Dense Index
  pinecone:
    api_key: ${PINECONE_API_KEY}
    environment: ${PINECONE_ENVIRONMENT}
    dense_index: "rag-dense"
    sparse_index: "rag-sparse"
    serverless_cloud: "aws"
    serverless_region: "us-east-1"
    
    # HNSW Index Parameters
    dense_hnsw:
      M: 16  # Number of connections per node
      ef_construction: 200  # Construction parameter
      ef_search: 40  # Query time parameter
  
  # PostgreSQL Metadata
  postgresql:
    host: ${DB_HOST}
    port: 5432
    database: rag_db
    user: ${DB_USER}
    password: ${DB_PASSWORD}
    pool_size: 20
    max_overflow: 0
  
  # Redis Cache
  redis:
    host: ${REDIS_HOST}
    port: 6379
    db: 0
    ttl_seconds: 604800  # 7 days
    max_memory_policy: "allkeys-lru"
  
  # Retrieval Configuration
  retrieval:
    dense_weight: 0.6
    sparse_weight: 0.4
    fusion_strategy: "rrf"  # rrf, weighted_sum, interleave
    max_retrieval_latency_ms: 100
    max_cache_size_gb: 10
    
  # Multi-tenancy
  multi_tenant:
    enabled: true
    default_tenant: "default"
    tenant_isolation: true  # Enforce filtering
```

---

## Part 9: Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Deployment Architecture                  │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Pinecone (Cloud-Managed)                               │ │
│  │ ├─ Dense Index: us-east-1 (serverless)                │ │
│  │ ├─ Sparse Index: us-east-1 (serverless)               │ │
│  │ └─ Auto-scaling, backups, monitoring                  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            ↑                                  │
│                      (vector storage)                         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ PostgreSQL (AWS RDS)                                   │ │
│  │ ├─ Multi-AZ, 100GB storage                             │ │
│  │ ├─ Full-text indexes, pgvector ext                    │ │
│  │ └─ Daily backups, 30-day retention                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            ↑                                  │
│                    (metadata, audit)                          │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Redis (AWS ElastiCache)                               │ │
│  │ ├─ Multi-AZ, 5GB cache                                 │ │
│  │ ├─ TTL-based eviction                                  │ │
│  │ └─ LRU replacement policy                              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            ↑                                  │
│                      (query cache)                            │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Application Servers (Python FastAPI)                  │ │
│  │ ├─ 3-5 instances (auto-scaling)                        │ │
│  │ ├─ LangGraph workflows                                 │ │
│  │ ├─ Connection pools to all data stores                 │ │
│  │ └─ LangSmith tracing integrated                        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## Part 10: SLA & Performance Targets

```
RETRIEVAL LATENCY SLA:

Dense Search:
  P50 (median): 20-30ms
  P95 (95th percentile): 50-80ms
  P99 (99th percentile): 100-150ms

Sparse Search:
  P50: 15-25ms
  P95: 40-60ms
  P99: 80-120ms

Hybrid Search (Dense + Sparse + Fusion):
  P50: 30-50ms
  P95: 80-120ms
  P99: 150-200ms

Cache Hit Latency:
  <5ms (direct Redis)

STORAGE CAPACITY:

Current Scale:
  - 1M chunks = ~1.5GB vectors (1536 dims @ 4 bytes)
  - 1M chunks metadata = ~500MB PostgreSQL
  - Hot cache: 10GB Redis

Scaling:
  - Pinecone handles up to 100M vectors easily
  - PostgreSQL: partition by date for retention
  - Redis: LRU eviction as cache fills

AVAILABILITY:

- Pinecone: 99.9% SLA (managed service)
- PostgreSQL: 99.95% (RDS Multi-AZ)
- Redis: 99.9% (ElastiCache Multi-AZ)
- Application: 99.95% (3 instances across AZs)
```

---

## Part 11: Data Layer as LEGO Brick Summary

Your Data Layer **perfectly fits** because:

✅ **Standardized Input**: Accepts exact Chunk structure from Ingestion
✅ **Standardized Output**: Returns RetrievedChunk format Reranking expects
✅ **Modular Storage**: Dense/Sparse/Metadata separate but coordinated
✅ **Clear Contracts**: Defined APIs for ingestion, retrieval, evaluation
✅ **Error Boundaries**: Cache/fallback if any layer fails
✅ **Observable**: Metrics, logging, tracing at every layer
✅ **Scalable**: Handles millions of chunks with <100ms latency
✅ **Multi-tenant**: Built-in user/tenant isolation
✅ **Feedback-ready**: Accepts quality scores from evaluation

**The Pipeline Fits Because**:
- Ingestion provides dense + sparse embeddings with metadata → Data Layer stores them
- Retrieval queries dense + sparse in parallel → Data Layer returns top-k
- Reranking refines results → Uses Data Layer's scores + metadata
- Generation cites sources → Data Layer provides original content
- Evaluation scores chunks → Feedback flows back to Data Layer

**Next Implementation Steps**:
1. Provision Pinecone project + indexes
2. Set up PostgreSQL RDS instance
3. Configure Redis ElastiCache
4. Build DataLayerService class
5. Implement hybrid search fusion
6. Add LangSmith monitoring
7. Load test at scale (10k+ queries)
8. Optimize based on latency measurements

