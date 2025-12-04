# Logging Framework Implementation - Production Code Examples

## Complete Python Implementation Guide

### 1. Core Logger Configuration (`config/logging_config.py`)

```python
"""
Production-grade logging configuration for RAG system
- Structured JSON output
- Multi-backend shipping
- Trace ID propagation
- Context management
"""

import structlog
import logging
import sys
from pythonjsonlogger import jsonlogger
from typing import Dict, Any
import contextvars
import json

# Context Variables (Thread-safe, AsyncIO-safe)
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "span_id", default=""
)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id", default=""
)
tenant_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tenant_id", default=""
)


class ContextFilter(logging.Filter):
    """Add context variables to every log record"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.span_id = span_id_var.get()
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.tenant_id = tenant_id_var.get()
        return True


def setup_logging(environment: str = "production", log_level: str = "INFO"):
    """
    Configure structlog + standard logging
    
    Args:
        environment: "development" | "production"
        log_level: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    """
    
    # Standard logging formatter (for non-structlog loggers)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(timestamp)s %(level)s %(name)s %(message)s",
        timestamp=True
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ContextFilter())
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        handlers=[console_handler]
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return logging.getLogger(__name__)


# Usage
setup_logging(environment="production", log_level="INFO")
logger = structlog.get_logger("rag")
```

---

### 2. Trace Context Manager (`core/tracing.py`)

```python
"""
Distributed trace management
- Creates unique trace IDs
- Manages span hierarchy
- Propagates context
- Integrates with LangSmith
"""

import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager, contextmanager
import contextvars
import structlog
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

logger = structlog.get_logger("rag.tracing")

# Context variables
trace_id_var = contextvars.ContextVar("trace_id")
span_id_var = contextvars.ContextVar("span_id")
parent_span_id_var = contextvars.ContextVar("parent_span_id", default=None)


class TraceContext:
    """
    Manages trace context for a request
    One trace = one request
    One trace contains many spans
    """
    
    def __init__(self, 
                 user_id: str = None,
                 tenant_id: str = None,
                 request_type: str = None):
        self.trace_id = str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())
        self.parent_span_id = None
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.request_type = request_type
        self.start_time = time.time()
        self.spans: Dict[str, Dict[str, Any]] = {}
    
    def new_span(self, span_name: str) -> str:
        """Create a child span"""
        parent_id = self.span_id
        self.span_id = str(uuid.uuid4())
        self.parent_span_id = parent_id
        
        self.spans[self.span_id] = {
            "name": span_name,
            "parent": parent_id,
            "start_time": time.time()
        }
        
        return self.span_id
    
    def get_duration_ms(self) -> float:
        """Total trace duration"""
        return (time.time() - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "request_type": self.request_type,
            "duration_ms": self.get_duration_ms()
        }


@contextmanager
def trace_span(span_name: str, trace_ctx: Optional[TraceContext] = None):
    """
    Context manager for creating spans
    
    Usage:
        with trace_span("file_parsing"):
            parse_file(...)  # Timed operation
    """
    
    ctx = trace_ctx or TraceContext()
    span_id = ctx.new_span(span_name)
    start_time = time.time()
    
    # Set context variables
    old_trace = trace_id_var.get() if trace_id_var in contextvars.copy_context() else None
    old_span = span_id_var.get() if span_id_var in contextvars.copy_context() else None
    
    trace_id_var.set(ctx.trace_id)
    span_id_var.set(span_id)
    
    logger = structlog.get_logger(f"rag.{span_name}")
    
    try:
        logger.info(f"{span_name}_started")
        yield ctx
        
        duration = (time.time() - start_time) * 1000
        logger.info(f"{span_name}_completed", duration_ms=duration)
        
    except Exception as e:
        logger.error(f"{span_name}_failed", error=str(e))
        raise
    
    finally:
        # Restore context
        if old_trace:
            trace_id_var.set(old_trace)
        if old_span:
            span_id_var.set(old_span)


def create_request_context(user_id: str, tenant_id: str) -> TraceContext:
    """Initialize context for new request"""
    ctx = TraceContext(user_id=user_id, tenant_id=tenant_id)
    trace_id_var.set(ctx.trace_id)
    span_id_var.set(ctx.span_id)
    return ctx
```

---

### 3. Log Aggregator & Shipping (`core/log_aggregator.py`)

```python
"""
Ship logs to multiple backends simultaneously
- LangSmith (traces + correlation)
- PostgreSQL (storage + querying)
- Datadog (optional analytics)
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
import structlog
from datetime import datetime
import psycopg_pool

logger = structlog.get_logger("rag.log_aggregator")


class LogAggregator:
    """Multi-backend log shipping"""
    
    def __init__(self, 
                 database_url: str,
                 datadog_enabled: bool = False):
        self.db_pool = psycopg_pool.AsyncConnectionPool(database_url)
        self.datadog_enabled = datadog_enabled
        self.queue: asyncio.Queue = asyncio.Queue()
        
        # Start background worker
        asyncio.create_task(self._worker())
    
    async def _worker(self):
        """Background worker that ships logs"""
        batch = []
        
        while True:
            try:
                # Collect logs
                log_entry = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                batch.append(log_entry)
                
                # Ship when batch is full
                if len(batch) >= 100:
                    await self._ship_batch(batch)
                    batch = []
                    
            except asyncio.TimeoutError:
                # Timeout: ship whatever we have
                if batch:
                    await self._ship_batch(batch)
                    batch = []
    
    async def log(self, log_entry: Dict[str, Any]):
        """Queue log for shipping"""
        await self.queue.put(log_entry)
    
    async def _ship_batch(self, batch: List[Dict[str, Any]]):
        """Ship batch to all backends"""
        
        try:
            # 1. PostgreSQL
            await self._ship_to_postgres(batch)
            
            # 2. Datadog
            if self.datadog_enabled:
                await self._ship_to_datadog(batch)
            
            logger.info("logs_shipped", count=len(batch))
            
        except Exception as e:
            logger.error("log_shipping_failed", error=str(e))
    
    async def _ship_to_postgres(self, batch: List[Dict[str, Any]]):
        """Store logs in PostgreSQL"""
        async with await self.db_pool.connection() as conn:
            for log_entry in batch:
                await conn.execute("""
                    INSERT INTO logs (
                        timestamp,
                        trace_id,
                        span_id,
                        request_id,
                        user_id,
                        tenant_id,
                        logger,
                        level,
                        message,
                        context,
                        metrics,
                        environment
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    datetime.fromisoformat(log_entry.get("timestamp", "")),
                    log_entry.get("trace_id"),
                    log_entry.get("span_id"),
                    log_entry.get("request_id"),
                    log_entry.get("user_id"),
                    log_entry.get("tenant_id"),
                    log_entry.get("logger"),
                    log_entry.get("level"),
                    log_entry.get("message"),
                    json.dumps(log_entry.get("context", {})),
                    json.dumps(log_entry.get("metrics", {})),
                    log_entry.get("environment", "production")
                ))
            
            await conn.commit()
    
    async def _ship_to_datadog(self, batch: List[Dict[str, Any]]):
        """Ship to Datadog (optional)"""
        # Implementation depends on Datadog SDK
        pass
    
    async def query_logs(self, 
                        trace_id: str = None,
                        user_id: str = None,
                        start_time: datetime = None,
                        end_time: datetime = None) -> List[Dict]:
        """Query logs from PostgreSQL"""
        
        query = "SELECT * FROM logs WHERE 1=1"
        params = []
        
        if trace_id:
            query += " AND trace_id = %s"
            params.append(trace_id)
        
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        
        if start_time:
            query += " AND timestamp >= %s"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= %s"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT 1000"
        
        async with await self.db_pool.connection() as conn:
            rows = await conn.execute(query, params)
            return rows
```

---

### 4. FastAPI Integration (`api/logging_middleware.py`)

```python
"""
Middleware for FastAPI
- Extract/create trace IDs from headers
- Propagate context through request
- Log request lifecycle
"""

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import uuid
import time
from typing import Callable

logger = structlog.get_logger("rag.api")

# Context variables
trace_id_var = contextvars.ContextVar("trace_id")
request_id_var = contextvars.ContextVar("request_id")
user_id_var = contextvars.ContextVar("user_id")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Extracts trace ID from headers (or creates new one)
    2. Sets context variables
    3. Logs request/response
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        
        # Extract or create trace ID
        trace_id = request.headers.get(
            "X-Trace-ID",
            str(uuid.uuid4())
        )
        request_id = f"req-{uuid.uuid4()}"
        user_id = request.headers.get("X-User-ID", "anonymous")
        
        # Set context
        trace_id_var.set(trace_id)
        request_id_var.set(request_id)
        user_id_var.set(user_id)
        
        # Log request
        logger.info(
            "http_request_received",
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            trace_id=trace_id
        )
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Log response
            duration = (time.time() - start_time) * 1000
            logger.info(
                "http_response_sent",
                status_code=response.status_code,
                duration_ms=duration,
                trace_id=trace_id
            )
            
            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except Exception as e:
            logger.error(
                "http_request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=(time.time() - start_time) * 1000,
                trace_id=trace_id
            )
            raise


def setup_logging_middleware(app: FastAPI):
    """Add logging middleware to FastAPI app"""
    app.add_middleware(LoggingMiddleware)
```

---

### 5. Database Schema (`migrations/create_logs_table.sql`)

```sql
-- Logs table for PostgreSQL
CREATE TABLE IF NOT EXISTS logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    trace_id UUID,
    span_id UUID,
    request_id VARCHAR(255),
    user_id VARCHAR(255),
    tenant_id VARCHAR(255),
    logger VARCHAR(255),
    level VARCHAR(20),
    message TEXT,
    context JSONB,
    metrics JSONB,
    error JSONB,
    stack_trace TEXT,
    environment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_trace_id (trace_id),
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_level (level),
    INDEX idx_request_id (request_id)
);

-- Retention policy: Keep 7 days of hot logs
CREATE POLICY logs_retention
    ON logs
    AS (timestamp > now() - INTERVAL '7 days');

-- Archive table for warm storage (30 days sampled)
CREATE TABLE IF NOT EXISTS logs_archive (
    LIKE logs
);

-- Metrics table for time-series
CREATE TABLE IF NOT EXISTS request_metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    trace_id UUID,
    operation VARCHAR(100),
    duration_ms FLOAT,
    status VARCHAR(20),
    user_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_operation_timestamp (operation, timestamp),
    INDEX idx_trace_id (trace_id)
);
```

---

### 6. Example: Instrumented Ingestion (`ingestion/pipeline.py`)

```python
"""
Ingestion pipeline with comprehensive logging
"""

from core.tracing import trace_span, TraceContext, create_request_context
from core.log_aggregator import LogAggregator
import structlog
import time

logger = structlog.get_logger("rag.ingestion")
aggregator = LogAggregator(database_url="postgresql://...")


async def ingest_file(file_path: str, user_id: str, tenant_id: str):
    """
    Complete ingestion pipeline with logging at each stage
    """
    
    # Create trace context
    trace_ctx = create_request_context(user_id, tenant_id)
    
    logger.info("ingestion_started",
                file_path=file_path,
                trace_id=trace_ctx.trace_id)
    
    try:
        # Stage 1: Parsing
        with trace_span("file_parsing", trace_ctx) as ctx:
            documents = await parse_file(file_path)
            logger.info("documents_parsed",
                       count=len(documents),
                       trace_id=ctx.trace_id)
        
        # Stage 2: Chunking
        with trace_span("document_chunking", trace_ctx) as ctx:
            chunks = await chunk_documents(documents)
            logger.info("chunks_created",
                       count=len(chunks),
                       avg_size=sum(len(c) for c in chunks) / len(chunks),
                       trace_id=ctx.trace_id)
        
        # Stage 3: Enrichment
        with trace_span("chunk_enrichment", trace_ctx) as ctx:
            enriched = await enrich_chunks(chunks)
            logger.info("chunks_enriched",
                       count=len(enriched),
                       trace_id=ctx.trace_id)
        
        # Stage 4: Embedding
        with trace_span("chunk_embedding", trace_ctx) as ctx:
            embedded = await embed_chunks(enriched)
            logger.info("chunks_embedded",
                       count=len(embedded),
                       cost_usd=calculate_embedding_cost(len(embedded)),
                       trace_id=ctx.trace_id)
        
        # Stage 5: Storage
        with trace_span("data_storage", trace_ctx) as ctx:
            stored_ids = await store_chunks(embedded)
            logger.info("chunks_stored",
                       count=len(stored_ids),
                       trace_id=ctx.trace_id)
        
        # Final success log
        logger.info("ingestion_completed",
                   total_chunks=len(embedded),
                   total_duration_ms=ctx.get_duration_ms(),
                   status="success",
                   trace_id=ctx.trace_id)
        
        return stored_ids
        
    except Exception as e:
        logger.error("ingestion_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    trace_id=trace_ctx.trace_id)
        raise
```

---

### 7. Query Debugging (`tools/log_query.py`)

```python
"""
Helper script to query logs for debugging
"""

import asyncio
from core.log_aggregator import LogAggregator
from datetime import datetime, timedelta

aggregator = LogAggregator(database_url="postgresql://...")


async def debug_trace(trace_id: str):
    """Get full trace for a request"""
    logs = await aggregator.query_logs(trace_id=trace_id)
    
    print(f"\n=== TRACE: {trace_id} ===\n")
    
    for log in logs:
        timestamp = log['timestamp']
        level = log['level']
        message = log['message']
        duration = log.get('metrics', {}).get('duration_ms', '-')
        
        print(f"{timestamp} [{level:8}] {message:30} {duration}ms")
    
    print(f"\nTotal logs: {len(logs)}")


async def find_errors(user_id: str, hours: int = 24):
    """Find all errors for a user"""
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    logs = await aggregator.query_logs(
        user_id=user_id,
        start_time=start_time
    )
    
    errors = [log for log in logs if log['level'] in ('ERROR', 'CRITICAL')]
    
    print(f"\n=== ERRORS for {user_id} (last {hours}h) ===\n")
    
    for error in errors:
        print(f"[{error['timestamp']}] {error['message']}")
        print(f"  Trace: {error['trace_id']}")
        print(f"  Error: {error.get('error')}\n")


if __name__ == "__main__":
    # Example usage
    trace_id = "550e8400-e29b-41d4-a716-446655440000"
    asyncio.run(debug_trace(trace_id))
```

---

## Usage in Your UI Ingestion Tab

```python
# When user uploads file in React UI:
# POST /api/ingest

@app.post("/api/ingest")
async def ingest_endpoint(file: UploadFile, user_id: str = Header(...)):
    """Ingestion endpoint with full logging"""
    
    # Middleware automatically sets trace_id
    # We just need to call the pipeline
    
    try:
        result = await ingest_file(
            file_path=file.filename,
            user_id=user_id,
            tenant_id=get_tenant_from_user(user_id)
        )
        
        return {
            "status": "success",
            "chunks_created": len(result),
            "trace_id": trace_id_var.get()  # Return for debugging
        }
    
    except Exception as e:
        # Errors automatically logged with trace_id
        return {"status": "error", "message": str(e)}
```

This implementation creates a production-grade logging system that tracks every operation through your RAG pipeline! 🎉
