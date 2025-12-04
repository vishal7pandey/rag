# Ingestion Pipeline Design - Production RAG System

## Executive Summary

The **Ingestion Pipeline** is the offline foundation that transforms raw uploaded files into queryable, embeddable chunks stored in your vector database. It operates as a **LangGraph workflow** where each step is a modular node, enabling:

- **Streaming updates** to the UI during processing
- **Error recovery** without losing progress
- **Feedback integration** from evaluation later
- **LangSmith monitoring** for debugging and optimization

This design treats ingestion as a **LEGO brick** that outputs standardized Chunk objects with dense/sparse embeddings, fitting perfectly into the Retrieval → Reranking → Generation → Evaluation feedback loop.

---

## Part 1: Architecture Overview

### Ingestion Pipeline Lego Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE (LangGraph)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │   FILE UPLOAD│──→│  VALIDATE    │──→│ PREPROCESS   │         │
│  │   & RECEIVE  │   │   & DETECT   │   │  & EXTRACT   │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│         │                                       │                 │
│         └───────────────────────────────────────┘                 │
│                       UI: "Received file"                         │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │   CHUNKING   │──→│  ENRICHMENT  │──→│  EMBEDDING   │         │
│  │   (Semantic) │   │  (Metadata)  │   │   (Dense     │         │
│  │              │   │              │   │   + Sparse)  │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│         │                                       │                 │
│         └───────────────────────────────────────┘                 │
│    UI: "Processed 45 chunks" / "Embedding 120 docs"             │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │   STORAGE    │   │  INDEXING    │   │  MONITORING  │         │
│  │   (Vector DB │──→│  & PERSIST   │──→│  & FEEDBACK  │         │
│  │   + Metadata)│   │              │   │              │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│                                                   │               │
│                                    UI: "Indexed 150 chunks"      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ OUTPUT: List[Chunk] → Ready for Retrieval              │    │
│  │ ├─ id, content, metadata                               │    │
│  │ ├─ dense_embedding (384/768/1536 dims)                │    │
│  │ ├─ sparse_embedding (BM25 scores)                      │    │
│  │ ├─ quality_score, created_at, etc.                     │    │
│  │ └─ All stored in vector DB with full-text index        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Component Design

### 2.1 Input Contract (UI → Ingestion)

```python
# Frontend sends this to backend API
class FileUploadRequest:
    files: List[UploadFile]  # From React UI
    document_metadata: Dict[str, str] = {
        "source": "user_upload",
        "category": "general",  # or "technical", "legal", etc.
        "language": "en"
    }
    ingestion_config: Dict = {
        "chunk_size_tokens": 512,
        "chunk_overlap_tokens": 50,
        "chunking_strategy": "semantic",  # or "fixed", "hierarchical"
        "embedding_model": "text-embedding-3-small",  # OpenAI model
        "compute_sparse": True,  # BM25 embeddings
        "enrich_metadata": True,
        "enrich_summaries": False  # Heavy operation, optional
    }

# Backend API endpoint
@app.post("/api/ingest")
async def ingest_files(request: FileUploadRequest):
    # Triggers LangGraph workflow
    result = await ingestion_graph.ainvoke(request)
    return result
```

### 2.2 Output Contract (Ingestion → Data Layer)

```python
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class Chunk:
    """Core data unit flowing through entire RAG system"""
    
    # Unique Identification
    id: UUID  # Generated automatically
    document_id: UUID  # Links to source document
    chunk_index: int  # Position in document (0, 1, 2, ...)
    
    # Content
    content: str  # Processed text, 300-800 tokens typically
    original_content: str  # Pre-processing, for debugging
    
    # Embeddings (MUST EXIST for retrieval to work)
    dense_embedding: List[float]  # 384/768/1536 dimensions, normalized
    sparse_embedding: Dict[str, float] = field(default_factory=dict)  # {"term": 2.5, ...}
    embedding_model: str = "text-embedding-3-small"
    embedding_generated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata (for filtering, attribution)
    metadata: Dict = field(default_factory=dict)
    # Standard fields:
    #   - source: str (filename or path)
    #   - document_type: str (pdf, txt, docx)
    #   - page_number: int
    #   - section_title: str
    #   - language: str (en, fr, etc.)
    #   - created_at: Timestamp
    #   - updated_at: Timestamp
    #   - user_id: str (for multi-user systems)
    #   - custom_field: Any (domain-specific)
    
    # Quality & Scoring (populated by ingestion)
    quality_score: Optional[float] = None  # 0.0-1.0
    has_valid_embedding: bool = True  # Sanity check
    is_duplicate: bool = False  # Duplicate detection result
    
    # Tracing & Attribution (for evaluation feedback)
    retrieval_rank: Optional[int] = None  # Set after retrieval
    reranking_rank: Optional[int] = None  # Set after reranking
    used_in_generation: bool = False  # Set if cited in response
    
    # Relationships
    parent_summary: Optional[str] = None  # For hierarchical RAG
    related_chunk_ids: List[UUID] = field(default_factory=list)  # Siblings

# Batch output
@dataclass
class IngestionResult:
    batch_id: UUID
    document_id: UUID
    status: str  # "success", "partial", "failed"
    chunks_created: List[Chunk]
    total_chunks: int
    failed_chunks: int
    errors: List[Dict] = field(default_factory=list)
    ingestion_duration_ms: float
    embedding_duration_ms: float
    storage_duration_ms: float
    monitoring_signals: Dict = field(default_factory=dict)
```

---

## Part 3: LangGraph Workflow Implementation

### 3.1 Complete LangGraph State Machine

```python
from typing import TypedDict, List, Optional
from langraph.graph import StateGraph
from uuid import uuid4
import logging

# Configure LangSmith monitoring
import langsmith
langsmith.configure_langsmith(project_name="rag-ingestion")

logger = logging.getLogger(__name__)

class IngestionState(TypedDict):
    """State object flowing through LangGraph nodes"""
    
    # Input
    uploaded_files: List[UploadFile]
    user_id: str
    ingestion_config: Dict
    
    # Processing state
    batch_id: UUID
    document_id: UUID
    current_step: str
    progress: float  # 0.0 to 1.0
    
    # Intermediate results
    extracted_texts: List[Dict]  # [{filename, content, metadata}]
    preprocessed_texts: List[Dict]  # [{filename, content, cleaned}]
    chunks: List[Dict]  # [{content, metadata, chunk_index}]
    enriched_chunks: List[Dict]  # [{...chunk, summary, entities}]
    embedded_chunks: List[Chunk]  # Fully formed Chunk objects
    
    # Status
    errors: List[Dict]
    warnings: List[Dict]
    ui_updates: List[str]  # Messages to send to UI
    
    # Output
    result: Optional[IngestionResult] = None

# Build LangGraph
workflow = StateGraph(IngestionState)

# STEP 1: Receive & Validate
def step_receive_and_validate(state: IngestionState) -> IngestionState:
    """
    Node 1: Validate files, detect format, initialize batch
    
    CONTRACT:
    - Input: uploaded_files (List[UploadFile])
    - Output: extracted_texts, batch_id, errors
    - Time: ~100ms for 5 files
    """
    batch_id = uuid4()
    extracted_texts = []
    errors = []
    
    logger.info(f"[INGEST] Starting batch {batch_id} with {len(state['uploaded_files'])} files")
    
    for i, file in enumerate(state['uploaded_files']):
        try:
            # Validate file
            if file.size > 50 * 1024 * 1024:  # 50MB limit
                raise ValueError(f"File too large: {file.size} bytes")
            
            if file.content_type not in [
                "application/pdf",
                "text/plain",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/csv"
            ]:
                raise ValueError(f"Unsupported format: {file.content_type}")
            
            # Read content
            content = file.file.read().decode('utf-8', errors='ignore')
            
            extracted_texts.append({
                "filename": file.filename,
                "content": content,
                "content_type": file.content_type,
                "file_size": file.size,
                "user_metadata": state['ingestion_config'].get('document_metadata', {})
            })
            
            progress = (i + 1) / len(state['uploaded_files']) * 0.1  # 10% of total
            state['ui_updates'].append(f"✓ Validated {file.filename}")
            
        except Exception as e:
            logger.error(f"Validation error for {file.filename}: {e}")
            errors.append({
                "file": file.filename,
                "step": "validation",
                "error": str(e)
            })
    
    state['batch_id'] = batch_id
    state['document_id'] = uuid4()  # One document_id per upload batch
    state['extracted_texts'] = extracted_texts
    state['errors'] = errors
    state['current_step'] = "validated"
    state['progress'] = 0.1
    
    return state

# STEP 2: Preprocess & Extract
def step_preprocess(state: IngestionState) -> IngestionState:
    """
    Node 2: Extract text, detect language, clean content
    
    CONTRACT:
    - Input: extracted_texts
    - Output: preprocessed_texts (cleaned, language detected)
    - Time: ~50-200ms depending on file size
    """
    from langchain_community.document_loaders import PDFPlumberLoader, TextLoader
    import re
    from langdetect import detect
    
    preprocessed_texts = []
    total_files = len(state['extracted_texts'])
    
    for i, doc_dict in enumerate(state['extracted_texts']):
        try:
            content = doc_dict['content']
            
            # Detect language
            try:
                language = detect(content[:500])  # Detect from first 500 chars
            except:
                language = "en"
            
            # Clean content
            # Remove extra whitespace
            content = re.sub(r'\s+', ' ', content)
            # Remove control characters
            content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\t')
            # Remove URLs (optional)
            content = re.sub(r'https?://\S+', '', content)
            
            preprocessed_texts.append({
                **doc_dict,
                "content": content,
                "language": language,
                "word_count": len(content.split()),
                "char_count": len(content)
            })
            
            progress = 0.1 + (i + 1) / total_files * 0.15  # 10-25% of total
            state['ui_updates'].append(
                f"📄 Preprocessed {doc_dict['filename']} (lang: {language}, "
                f"words: {len(content.split())})"
            )
            
        except Exception as e:
            logger.error(f"Preprocessing error: {e}")
            state['errors'].append({
                "file": doc_dict.get('filename'),
                "step": "preprocess",
                "error": str(e)
            })
    
    state['preprocessed_texts'] = preprocessed_texts
    state['current_step'] = "preprocessed"
    state['progress'] = 0.25
    
    return state

# STEP 3: Chunking
def step_chunk(state: IngestionState) -> IngestionState:
    """
    Node 3: Split content into chunks using semantic strategy
    
    CONTRACT:
    - Input: preprocessed_texts, chunking_strategy
    - Output: chunks (List[Dict] with content, metadata, chunk_index)
    - Time: ~100-300ms depending on document size
    
    STRATEGIES:
    - fixed: Fixed token size (e.g., 512 tokens)
    - semantic: Split on sentence boundaries, merge for coherence
    - hierarchical: Preserve document structure (chapters → sections → chunks)
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter, SentenceTransformers
    
    chunks = []
    chunk_size = state['ingestion_config'].get('chunk_size_tokens', 512)
    overlap = state['ingestion_config'].get('chunk_overlap_tokens', 50)
    strategy = state['ingestion_config'].get('chunking_strategy', 'semantic')
    
    chunk_index = 0
    
    for doc_dict in state['preprocessed_texts']:
        try:
            content = doc_dict['content']
            
            if strategy == "fixed":
                # Simple character-based splitting
                # ~4 chars per token, so multiply chunk_size by 4
                char_size = chunk_size * 4
                char_overlap = overlap * 4
                
                for i in range(0, len(content), char_size - char_overlap):
                    chunk_text = content[i:i + char_size]
                    if len(chunk_text.strip()) > 50:  # Minimum chunk size
                        chunks.append({
                            "content": chunk_text,
                            "metadata": {
                                **doc_dict['user_metadata'],
                                "source": doc_dict['filename'],
                                "document_type": doc_dict['content_type'],
                                "language": doc_dict['language'],
                                "chunk_index": chunk_index
                            },
                            "chunk_index": chunk_index
                        })
                        chunk_index += 1
            
            elif strategy == "semantic":
                # LangChain's semantic chunking
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=char_size,
                    chunk_overlap=char_overlap,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                split_texts = splitter.split_text(content)
                
                for chunk_text in split_texts:
                    if len(chunk_text.strip()) > 50:
                        chunks.append({
                            "content": chunk_text,
                            "metadata": {
                                **doc_dict['user_metadata'],
                                "source": doc_dict['filename'],
                                "document_type": doc_dict['content_type'],
                                "language": doc_dict['language'],
                                "chunk_index": chunk_index
                            },
                            "chunk_index": chunk_index
                        })
                        chunk_index += 1
            
            state['ui_updates'].append(
                f"✂️ Chunked {doc_dict['filename']}: {chunk_index} chunks"
            )
            
        except Exception as e:
            logger.error(f"Chunking error: {e}")
            state['errors'].append({
                "file": doc_dict.get('filename'),
                "step": "chunking",
                "error": str(e)
            })
    
    state['chunks'] = chunks
    state['current_step'] = "chunked"
    state['progress'] = 0.4
    
    return state

# STEP 4: Enrichment
def step_enrich(state: IngestionState) -> IngestionState:
    """
    Node 4: Add metadata, summaries, entities
    
    CONTRACT:
    - Input: chunks
    - Output: enriched_chunks (with summaries, entities, keywords)
    - Time: ~200-500ms (calls LLM for summaries)
    - Optional: Can skip for faster ingestion
    """
    from langchain_openai import ChatOpenAI
    from langchain.prompts import PromptTemplate
    from langchain.chains import LLMChain
    
    enrich = state['ingestion_config'].get('enrich_metadata', True)
    enrich_summaries = state['ingestion_config'].get('enrich_summaries', False)
    
    enriched_chunks = []
    
    if not enrich:
        # Skip enrichment, pass through
        state['ui_updates'].append("⏭️ Skipping enrichment (disabled)")
        return {**state, 'enriched_chunks': state['chunks']}
    
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    
    for i, chunk_dict in enumerate(state['chunks']):
        enriched = {**chunk_dict}
        
        try:
            # Extract entities (simple approach)
            entities = extract_entities(chunk_dict['content'])
            enriched['metadata']['entities'] = entities
            
            # Extract keywords
            keywords = extract_keywords(chunk_dict['content'])
            enriched['metadata']['keywords'] = keywords
            
            # Optional: Generate summary (expensive, skip for speed)
            if enrich_summaries and i < 5:  # Only first 5 chunks
                summary_prompt = PromptTemplate(
                    input_variables=["text"],
                    template="Summarize this in 1-2 sentences: {text}"
                )
                chain = LLMChain(llm=llm, prompt=summary_prompt)
                summary = chain.run(text=chunk_dict['content'][:500])
                enriched['summary'] = summary
            
            enriched_chunks.append(enriched)
            
        except Exception as e:
            logger.warning(f"Enrichment error for chunk {i}: {e}")
            enriched_chunks.append(chunk_dict)  # Fallback: use original
    
    state['ui_updates'].append(f"✨ Enriched {len(enriched_chunks)} chunks")
    state['enriched_chunks'] = enriched_chunks
    state['current_step'] = "enriched"
    state['progress'] = 0.6
    
    return state

# STEP 5: Embedding Generation
async def step_embed(state: IngestionState) -> IngestionState:
    """
    Node 5: Generate dense + sparse embeddings
    
    CONTRACT:
    - Input: enriched_chunks
    - Output: embedded_chunks (List[Chunk] with dense_embedding, sparse_embedding)
    - Time: ~500ms-2s (API calls to OpenAI embeddings)
    - Parallelized using batch API
    """
    from langchain_openai import OpenAIEmbeddings
    from langchain.embeddings.base import Embeddings
    import asyncio
    
    embedding_model = state['ingestion_config'].get('embedding_model', 'text-embedding-3-small')
    compute_sparse = state['ingestion_config'].get('compute_sparse', True)
    
    # OpenAI embeddings
    embeddings = OpenAIEmbeddings(model=embedding_model)
    
    embedded_chunks = []
    batch_size = 10  # Process in batches
    
    try:
        # Batch process for efficiency
        for batch_start in range(0, len(state['enriched_chunks']), batch_size):
            batch_end = min(batch_start + batch_size, len(state['enriched_chunks']))
            batch = state['enriched_chunks'][batch_start:batch_end]
            
            # Get dense embeddings (parallel)
            texts = [chunk['content'] for chunk in batch]
            dense_embeddings = await asyncio.gather(
                *[embeddings.aembed_query(text) for text in texts]
            )
            
            # Process each chunk
            for i, chunk_dict in enumerate(batch):
                chunk_id = uuid4()
                
                # Dense embedding
                dense_emb = dense_embeddings[i]
                
                # Sparse embedding (BM25)
                sparse_emb = {}
                if compute_sparse:
                    sparse_emb = compute_bm25_embedding(chunk_dict['content'])
                
                # Create Chunk object
                chunk = Chunk(
                    id=chunk_id,
                    document_id=state['document_id'],
                    chunk_index=chunk_dict['chunk_index'],
                    content=chunk_dict['content'],
                    original_content=chunk_dict['content'],
                    dense_embedding=dense_emb,
                    sparse_embedding=sparse_emb,
                    embedding_model=embedding_model,
                    metadata=chunk_dict['metadata'],
                    quality_score=0.8  # Default, updated by evaluation
                )
                
                embedded_chunks.append(chunk)
            
            progress = 0.6 + (batch_end / len(state['enriched_chunks'])) * 0.2
            state['ui_updates'].append(
                f"🔢 Embedded {batch_end}/{len(state['enriched_chunks'])} chunks"
            )
    
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        state['errors'].append({
            "step": "embedding",
            "error": str(e)
        })
    
    state['embedded_chunks'] = embedded_chunks
    state['current_step'] = "embedded"
    state['progress'] = 0.8
    
    return state

# STEP 6: Storage & Indexing
async def step_store(state: IngestionState) -> IngestionState:
    """
    Node 6: Store chunks in vector DB + metadata store
    
    CONTRACT:
    - Input: embedded_chunks (List[Chunk])
    - Output: IngestionResult with confirmed storage
    - Time: ~200-500ms (batch storage operation)
    """
    from pinecone import Pinecone
    
    try:
        # Initialize Pinecone (assumes credentials in env)
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index("rag-index")
        
        vectors_to_upsert = []
        
        for chunk in state['embedded_chunks']:
            # Prepare vector format for Pinecone
            vector = (
                str(chunk.id),  # id
                chunk.dense_embedding,  # vector
                {  # metadata
                    "content": chunk.content,
                    "source": chunk.metadata.get("source"),
                    "page_number": chunk.metadata.get("page_number"),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "language": chunk.metadata.get("language", "en")
                }
            )
            vectors_to_upsert.append(vector)
        
        # Upsert to Pinecone (batch)
        index.upsert(vectors=vectors_to_upsert)
        
        # Store metadata in PostgreSQL (if using)
        # db.batch_insert_chunks(state['embedded_chunks'])
        
        # Create full-text index for BM25 (if using Elasticsearch)
        # for chunk in state['embedded_chunks']:
        #     es_client.index(
        #         index="chunks",
        #         body={
        #             "content": chunk.content,
        #             "chunk_id": str(chunk.id),
        #             "metadata": chunk.metadata
        #         }
        #     )
        
        state['ui_updates'].append(
            f"💾 Stored {len(state['embedded_chunks'])} chunks in vector DB"
        )
        state['current_step'] = "stored"
        state['progress'] = 0.95
        
    except Exception as e:
        logger.error(f"Storage error: {e}")
        state['errors'].append({
            "step": "storage",
            "error": str(e)
        })
    
    return state

# STEP 7: Monitoring & Response
def step_finalize(state: IngestionState) -> IngestionState:
    """
    Node 7: Generate result, log metrics, update monitoring
    
    CONTRACT:
    - Input: All previous steps
    - Output: IngestionResult
    - Time: ~50ms
    """
    failed_count = len(state['errors'])
    total_count = len(state['embedded_chunks']) + failed_count
    
    result = IngestionResult(
        batch_id=state['batch_id'],
        document_id=state['document_id'],
        status="success" if failed_count == 0 else ("partial" if len(state['embedded_chunks']) > 0 else "failed"),
        chunks_created=state['embedded_chunks'],
        total_chunks=total_count,
        failed_chunks=failed_count,
        errors=state['errors'],
        ingestion_duration_ms=5000,  # Would calculate from timestamps
        embedding_duration_ms=2000,
        storage_duration_ms=500,
        monitoring_signals={
            "chunks_processed": len(state['embedded_chunks']),
            "avg_chunk_size": sum(len(c.content) for c in state['embedded_chunks']) / max(1, len(state['embedded_chunks'])),
            "embedding_model": state['ingestion_config'].get('embedding_model'),
            "user_id": state.get('user_id')
        }
    )
    
    state['result'] = result
    state['ui_updates'].append(
        f"✅ Ingestion Complete! {len(state['embedded_chunks'])} chunks indexed"
    )
    state['current_step'] = "completed"
    state['progress'] = 1.0
    
    # Send to monitoring/observability
    logger.info(f"Ingestion completed: {result}")
    
    return state

# Compose LangGraph
workflow.add_node("receive_validate", step_receive_and_validate)
workflow.add_node("preprocess", step_preprocess)
workflow.add_node("chunk", step_chunk)
workflow.add_node("enrich", step_enrich)
workflow.add_node("embed", step_embed)
workflow.add_node("store", step_store)
workflow.add_node("finalize", step_finalize)

# Edges (linear flow with conditional error handling)
workflow.add_edge("receive_validate", "preprocess")
workflow.add_edge("preprocess", "chunk")
workflow.add_edge("chunk", "enrich")
workflow.add_edge("enrich", "embed")
workflow.add_edge("embed", "store")
workflow.add_edge("store", "finalize")

workflow.set_entry_point("receive_validate")
workflow.set_finish_point("finalize")

# Compile
ingestion_graph = workflow.compile()
```

### 3.2 Helper Functions

```python
def extract_entities(text: str) -> List[Dict]:
    """Extract named entities using simple NER"""
    from langchain_experimental.ner import ner
    # Simplified version - production would use spaCy or specialized NER
    return []

def extract_keywords(text: str, top_k: int = 5) -> List[str]:
    """Extract top keywords using TF-IDF"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer(max_features=top_k)
    try:
        vectorizer.fit_transform([text])
        keywords = vectorizer.get_feature_names_out().tolist()
        return keywords[:top_k]
    except:
        return []

def compute_bm25_embedding(text: str) -> Dict[str, float]:
    """Compute BM25 term weights for sparse retrieval"""
    from rank_bm25 import BM25Okapi
    tokens = text.lower().split()
    bm25 = BM25Okapi([tokens])
    scores = bm25.get_scores([tokens])[0]
    
    # Return top terms with scores
    term_scores = {token: score for token, score in zip(tokens, scores)}
    return dict(sorted(term_scores.items(), key=lambda x: x[1], reverse=True)[:50])
```

---

## Part 4: API Endpoints

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

# Stream ingestion updates to UI
@app.post("/api/ingest")
async def ingest_files(files: List[UploadFile] = File(...)):
    """
    POST /api/ingest
    
    Uploads files and triggers ingestion pipeline with streaming updates
    """
    request = FileUploadRequest(
        files=files,
        document_metadata={"source": "ui_upload"},
        ingestion_config={}  # Use defaults
    )
    
    async def event_generator():
        """Stream updates to frontend"""
        initial_state = IngestionState(
            uploaded_files=files,
            user_id="default_user",
            ingestion_config=request.ingestion_config,
            batch_id=uuid4(),
            document_id=uuid4(),
            current_step="initiated",
            progress=0.0,
            extracted_texts=[],
            preprocessed_texts=[],
            chunks=[],
            enriched_chunks=[],
            embedded_chunks=[],
            errors=[],
            warnings=[],
            ui_updates=[]
        )
        
        # Run through ingestion graph
        final_state = await ingestion_graph.ainvoke(initial_state)
        
        # Stream updates
        for update in final_state['ui_updates']:
            yield f"data: {json.dumps({'message': update, 'progress': final_state['progress']})}\n\n"
        
        # Final result
        result = final_state['result']
        yield f"data: {json.dumps({'result': result.dict()})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Check ingestion status
@app.get("/api/ingest/status/{batch_id}")
async def ingest_status(batch_id: str):
    """Get status of ongoing ingestion"""
    # Would query cache/DB for status
    return {"batch_id": batch_id, "status": "processing"}

# Get ingestion metrics
@app.get("/api/ingest/metrics")
async def ingest_metrics():
    """Get ingestion metrics for monitoring"""
    return {
        "total_chunks_ingested": 1500,
        "avg_embedding_latency_ms": 45,
        "failed_ingestions": 2,
        "active_uploads": 1
    }
```

---

## Part 5: Integration Points (Lego Bricks Fitting Together)

### 5.1 Output → Data Layer (Retrieval's Input)

```python
# After ingestion completes, chunks are ready for retrieval
# The Chunk object contracts EXACTLY with Retrieval's input expectations

# Retrieval expects this:
class RetrievalRequest:
    query_embedding: List[float]  # Same dims as our chunk.dense_embedding ✓
    top_k: int
    filters: Dict  # Can filter on metadata ✓
    
# Retrieval receives this from storage:
retrieved_chunks: List[Chunk]  # Our exact output ✓
```

### 5.2 Feedback Loop ← Evaluation (Ingestion's Input Later)

```python
# After evaluation scores our chunks, feedback flows back

# Evaluation produces:
class EvaluationFeedback:
    chunk_id: UUID
    quality_score: float  # 0.0-1.0
    why_low: str  # "chunks_too_small", "poor_semantic_understanding", etc.

# Ingestion stores this for next iteration
# When re-ingesting same document:
# - Adjust chunk size if feedback says "chunks_too_small"
# - Switch embedding model if feedback says "poor_semantic_understanding"
# - This closes the feedback loop
```

### 5.3 Real-Time UI Updates

```javascript
// React Frontend - Ingestion Component
const [progress, setProgress] = useState(0);
const [messages, setMessages] = useState([]);

async function uploadFiles(files) {
    const eventSource = new EventSource('/api/ingest');
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setProgress(data.progress);
        setMessages(prev => [...prev, data.message]);
        
        if (data.result) {
            console.log('Ingestion complete:', data.result);
            eventSource.close();
        }
    };
}
```

---

## Part 6: Configuration & Monitoring

### 6.1 Configuration Schema

```yaml
# ingestion_config.yaml
ingestion:
  # File handling
  max_file_size_mb: 50
  supported_formats:
    - application/pdf
    - text/plain
    - application/vnd.openxmlformats-officedocument.wordprocessingml.document
  
  # Chunking
  chunking_strategy: "semantic"  # fixed, semantic, hierarchical
  chunk_size_tokens: 512
  chunk_overlap_tokens: 50
  min_chunk_size_chars: 100
  
  # Embedding
  embedding_model: "text-embedding-3-small"  # Small, fast, cheap (3-small)
  embedding_model_dimensions: 1536
  compute_sparse: true
  batch_size: 10
  
  # Enrichment
  enrich_metadata: true
  enrich_summaries: false  # Expensive
  extract_entities: true
  extract_keywords: true
  
  # Storage
  vector_db: "pinecone"
  metadata_store: "postgresql"
  
  # Monitoring
  enable_langsmith: true
  log_level: "INFO"
  max_parallel_uploads: 5
```

### 6.2 Monitoring Metrics

```python
# Metrics to track for optimization
ingestion_metrics = {
    "total_files_uploaded": 0,
    "total_chunks_created": 0,
    "avg_chunk_size_tokens": 0,
    "avg_preprocessing_latency_ms": 0,
    "avg_chunking_latency_ms": 0,
    "avg_enrichment_latency_ms": 0,
    "avg_embedding_latency_ms": 0,  # Most expensive
    "avg_storage_latency_ms": 0,
    "total_ingestion_latency_ms": 0,
    "error_rate": 0.0,
    "duplicate_chunks_detected": 0,
    "avg_embedding_quality_score": 0.0,
}

# Log to LangSmith for analysis
from langsmith import Client
client = Client()
client.log_metrics("ingestion", ingestion_metrics)
```

---

## Part 7: Error Handling & Recovery

```python
# Graceful degradation
error_recovery = {
    "embedding_api_timeout": {
        "action": "retry_with_smaller_batch",
        "max_retries": 3,
        "user_impact": "delay"
    },
    "unsupported_file_format": {
        "action": "skip_file",
        "max_retries": 0,
        "user_impact": "partial_failure"
    },
    "sparse_embedding_computation_error": {
        "action": "skip_sparse_embedding",
        "fallback": "use_dense_only",
        "user_impact": "reduced_functionality"
    }
}
```

---

## Part 8: Summary - Lego Brick Integration

Your Ingestion Pipeline is a **perfect LEGO brick** because:

✅ **Standardized Output**: Every chunk has the exact contract Data Layer expects
✅ **Modular Steps**: Each step in LangGraph is independent, reusable, testable
✅ **Clear Interfaces**: Defined input/output contracts prevent integration bugs
✅ **Error Boundaries**: Failures don't cascade; system degrades gracefully
✅ **Feedback Loop**: Evaluation results feed back to improve future ingestions
✅ **Monitoring Built-in**: LangSmith tracing for debugging and optimization
✅ **Scalable**: Async processing, batch APIs, parallel embedding generation
✅ **Observable**: UI updates, metrics, logging for full visibility

**The Pipeline Fits Because**:
- Dense embeddings (768 dims) → Retrieval's vector search
- Sparse embeddings (BM25) → Retrieval's keyword search
- Metadata → Retrieval's filters
- Chunk structure → Evaluation's input expectations
- Quality scores → Reranking and Generation's confidence

**Next Steps for Implementation**:
1. Set up Pinecone + PostgreSQL
2. Create OpenAI API embeddings integration
3. Build FastAPI endpoints with streaming
4. Create React ingestion UI
5. Add LangSmith monitoring
6. Test with sample documents
7. Optimize chunk size/embedding model based on retrieval metrics

