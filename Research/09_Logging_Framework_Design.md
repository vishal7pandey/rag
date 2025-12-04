# Logging Framework Design - Production RAG System
## "The Nervous System" - Structured Logging & Observability

## Executive Summary

The **Logging Framework** is the "nervous system" of your RAG system—it carries signals from every component back to central monitoring, enabling you to:

- **See what's happening** (structured logs with context)
- **Trace requests end-to-end** (distributed tracing with trace IDs)
- **Correlate across layers** (logs ↔ metrics ↔ traces)
- **Debug issues quickly** (rich context for root cause analysis)
- **Monitor health continuously** (real-time metrics + alerts)

This design treats logging as **pervasive instrumentation** using:

- **Structured JSON logging** (queryable, parseable, analyzable)
- **Distributed trace IDs** (follow requests through all layers)
- **Context propagation** (implicit request context via Python contextvars)
- **Multi-level aggregation** (LangSmith → Metrics → Dashboards)
- **Production-grade retention** (logs kept 7-30 days, indexed)

The framework operates as the **"veins of the system"**:
✓ Carries observability data from all components
✓ Routes to appropriate backends (LangSmith, metrics DB, logs DB)
✓ Correlates events across services/layers
✓ Enables root cause analysis
✓ Drives continuous improvement via feedback

---

## Part 1: Architecture Overview

### The Logging System - Three Pillars of Observability

```
┌─────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY FRAMEWORK                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Every Layer Instruments: Structured JSON Logs + Trace IDs       │
│  ├─ INGESTION: "File uploaded (3.2 MB)", "Chunking complete"   │
│  ├─ DATA: "Search query 50ms", "Cached result hit"              │
│  ├─ RETRIEVAL: "Hybrid search: 15 chunks retrieved"            │
│  ├─ GENERATION: "Token budget 3500/128000", "Stream started"   │
│  ├─ EVALUATION: "RAGAS score: 0.82 (good)"                     │
│  └─ MEMORY: "History stored (5 turns)"                          │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PILLAR 1: LOGS (Events & Context)                        │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  ├─ Structured JSON format                                │  │
│  │  ├─ Every log has: timestamp, level, logger, trace_id    │  │
│  │  ├─ Context: user_id, session_id, request_id             │  │
│  │  ├─ Queryable: "find all errors for user_id=123"        │  │
│  │  ├─ Storage: PostgreSQL logs table (7 day retention)      │  │
│  │  └─ Real-time: Ship to LangSmith + Datadog               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PILLAR 2: METRICS (Aggregated Signals)                   │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  ├─ Counters: requests, errors, queries                   │  │
│  │  ├─ Gauges: active connections, cache size               │  │
│  │  ├─ Histograms: latency, token count, cost               │  │
│  │  ├─ Storage: Prometheus (15 day retention)               │  │
│  │  └─ Dashboards: Grafana (real-time + historical)         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PILLAR 3: TRACES (Request Flow)                          │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  ├─ Spans: Each operation is a span (start→end time)     │  │
│  │  ├─ Nesting: Spans within spans (ingestion→chunking)     │  │
│  │  ├─ Trace ID: Links all spans for one query              │  │
│  │  ├─ Context: Span ID, parent ID, tags, attributes       │  │
│  │  ├─ Storage: LangSmith (30 day retention)                │  │
│  │  └─ Waterfall: See full request timeline visually        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  CORRELATION: The Real Magic                              │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  Trace ID in every log: Links logs → trace               │  │
│  │  Span ID in every metric: Links metrics → trace           │  │
│  │  Result: From 1 error → see entire request → fix it      │  │
│  │                                                             │  │
│  │  Example journey:                                          │  │
│  │  1. Dashboard shows spike in latency                      │  │
│  │  2. Click spike → finds correlated errors                │  │
│  │  3. Errors have trace IDs                                 │  │
│  │  4. View trace → see exact point of failure              │  │
│  │  5. Follow logs in that trace → root cause!              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  AGGREGATION & ANALYSIS                                   │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  ├─ Real-time alerting (latency > 2s)                    │  │
│  │  ├─ Trend analysis (quality degradation)                  │  │
│  │  ├─ Correlation (find related errors)                    │  │
│  │  ├─ Cost analysis (track per-component spend)             │  │
│  │  └─ Dashboards (executive visibility)                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Structured JSON Logging (The Core)

### 2.1 Log Format Standard

Every log MUST have this structure:

```json
{
  "timestamp": "2025-12-03T22:45:30.123Z",
  "level": "INFO",
  "logger": "rag.ingestion",
  "message": "File upload completed successfully",
  
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "f4dfc083-2e28-41da-9527-e3f0dc47cf45",
  "parent_span_id": "06f0ec30-d8f7-4d56-b2b8-f6e55b5f6f5f",
  
  "request_id": "req-2025-12-03-001",
  "user_id": "user-123",
  "session_id": "session-456",
  "tenant_id": "tenant-789",
  
  "context": {
    "action": "file_upload",
    "file_name": "report.pdf",
    "file_size_bytes": 3145728,
    "file_format": "pdf",
    "status": "success"
  },
  
  "metrics": {
    "duration_ms": 1250,
    "chunks_created": 42,
    "cost_usd": 0.012
  },
  
  "error": null,
  "stack_trace": null,
  
  "environment": "production",
  "version": "1.0.0",
  "host": "rag-server-01"
}
```

### 2.2 Python Implementation with structlog

```python
"""
Structured logging with structlog
Best library for production JSON logging in Python
"""

import structlog
import logging
from contextvars import ContextVar
from uuid import uuid4

# Context variables (implicitly propagated)
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

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
        structlog.processors.UnicodeDecoder(),
        
        # Custom processor: Add context variables
        lambda logger, method_name, event_dict: {
            **event_dict,
            "trace_id": trace_id_var.get() or str(uuid4()),
            "span_id": span_id_var.get() or str(uuid4()),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
        },
        
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# Get logger
logger = structlog.get_logger("rag.ingestion")

# Example usage
def upload_file(file_path: str, user_id: str):
    """Upload and process a file"""
    
    # Set context for this request
    request_id = f"req-{datetime.now().isoformat()}"
    trace_id = str(uuid4())
    
    request_id_var.set(request_id)
    user_id_var.set(user_id)
    trace_id_var.set(trace_id)
    
    logger.info(
        "file_upload_started",
        file_path=file_path,
        file_size_bytes=os.path.getsize(file_path)
    )
    
    try:
        # Process file...
        chunks = chunk_file(file_path)
        
        logger.info(
            "file_upload_completed",
            chunks_created=len(chunks),
            status="success"
        )
        
    except Exception as e:
        logger.error(
            "file_upload_failed",
            error=str(e),
            error_type=type(e).__name__,
            stack_trace=traceback.format_exc()
        )
        raise
```

---

## Part 3: Distributed Tracing (Trace IDs & Span IDs)

### 3.1 Creating and Propagating Trace IDs

**Key Principle**: Every request gets a unique trace ID. Every operation gets a unique span ID. Trace IDs are propagated through the entire request lifecycle.

```python
"""
Distributed tracing with LangSmith integration
"""

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from contextvars import ContextVar, copy_context
import asyncio

# Global trace context
current_trace_id: ContextVar[str] = ContextVar("trace_id")
current_span_id: ContextVar[str] = ContextVar("span_id")

class TraceContext:
    """Manages trace context for a request"""
    
    def __init__(self, user_id: str = None, request_type: str = None):
        self.trace_id = str(uuid4())
        self.span_id = str(uuid4())
        self.user_id = user_id
        self.request_type = request_type
        self.start_time = time.time()
    
    def child_span(self):
        """Create a child span (same trace, new span)"""
        self.span_id = str(uuid4())
        return self
    
    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "duration_ms": (time.time() - self.start_time) * 1000
        }

def create_trace_context(user_id: str = None) -> TraceContext:
    """Initialize trace context for a request"""
    ctx = TraceContext(user_id=user_id)
    current_trace_id.set(ctx.trace_id)
    current_span_id.set(ctx.span_id)
    return ctx

# LangSmith integration (automatic tracing)
@traceable(name="query_handler")
async def handle_query(query: str, user_id: str):
    """
    LangSmith automatically:
    1. Creates a span for this function
    2. Captures inputs/outputs
    3. Measures execution time
    4. Stores in LangSmith backend
    """
    
    # Get the trace context LangSmith created
    if run_tree := get_current_run_tree():
        trace_id = run_tree.id
        
        # Log it
        logger = structlog.get_logger("rag.retrieval")
        logger.info(
            "query_received",
            query=query,
            trace_id=str(trace_id)
        )
```

### 3.2 Propagating Across Layers

```python
"""
Trace ID flows through all layers automatically
"""

@traceable(name="ingestion_pipeline")
async def ingest_file(file_path: str):
    # LangSmith span 1: Ingestion
    
    # Automatic child span 2: Parsing
    with tracer.span("parsing") as span:
        documents = await parse_file(file_path)
    
    # Automatic child span 3: Chunking
    with tracer.span("chunking") as span:
        chunks = await chunk_documents(documents)
    
    # Automatic child span 4: Embedding
    with tracer.span("embedding") as span:
        embedded_chunks = await embed_chunks(chunks)
    
    # Automatic child span 5: Storage
    with tracer.span("storage") as span:
        await store_chunks(embedded_chunks)
    
    # Result: LangSmith shows:
    # - Parent span (ingestion_pipeline)
    # - Child spans: parsing, chunking, embedding, storage
    # - Times for each
    # - All linked by single trace_id
```

---

## Part 4: Log Levels & Context

### 4.1 Log Level Strategy

```python
"""
Structured log levels for production RAG
"""

import logging

# Log levels define verbosity:
# - DEBUG (1000+): Everything (file sizes, variable values, etc.)
# - INFO (500+): Normal operations (started, completed, milestone)
# - WARNING (200+): Unexpected but handled (slow operation, retry)
# - ERROR (50+): Operation failed (API error, invalid input)
# - CRITICAL (10+): System down (database offline, out of memory)

logger = structlog.get_logger("rag.generation")

def generate_response(query: str, chunks: List[str]):
    """Example of multi-level logging"""
    
    logger.debug(
        "generate_start",
        query_tokens=len(query.split()),
        context_tokens=sum(len(c.split()) for c in chunks)
    )  # DEBUG: Detailed metrics
    
    logger.info(
        "token_budget_allocated",
        total_budget=128000,
        allocated_query=len(query.split()),
        allocated_context=2000,
        allocated_response=1000
    )  # INFO: Key milestone
    
    try:
        if generation_time > 5.0:
            logger.warning(
                "slow_generation",
                generation_time_ms=generation_time * 1000,
                model="gpt-4o",
                threshold_ms=5000
            )  # WARNING: Performance issue
        
        response = call_openai_api(prompt)
        
        logger.info(
            "generation_complete",
            tokens_used=response.usage.total_tokens,
            cost_usd=calculate_cost(response.usage),
            status="success"
        )  # INFO: Successful completion
        
    except RateLimitError as e:
        logger.warning(
            "rate_limit_hit",
            error=str(e),
            retry_after_seconds=60,
            action="queued_for_retry"
        )  # WARNING: Handled gracefully
        
    except APIError as e:
        logger.error(
            "openai_api_failed",
            error=str(e),
            model="gpt-4o",
            error_code=e.error_code,
            action="fallback_to_mini"
        )  # ERROR: Operation failed, fallback triggered
        
    except SystemError as e:
        logger.critical(
            "system_error",
            error=str(e),
            error_type=type(e).__name__,
            stack_trace=traceback.format_exc(),
            action="shutdown"
        )  # CRITICAL: System-level failure
```

### 4.2 Context Binding

```python
"""
Bind context once, it appears in all logs from that logger
"""

# Create bound logger with request context
def create_request_logger(user_id: str, request_id: str):
    logger = structlog.get_logger("rag")
    
    # Bind context
    return logger.bind(
        user_id=user_id,
        request_id=request_id,
        tenant_id=get_tenant_for_user(user_id),
        session_id=generate_session_id()
    )

# Usage
logger = create_request_logger("user-123", "req-001")

# All these logs will automatically include user_id, request_id, tenant_id, session_id
logger.info("query_started", query="what is X?")
logger.info("retrieval_started", chunks_needed=5)
logger.info("generation_started", model="gpt-4o")

# Result: Every log has full context automatically
```

---

## Part 5: Real-Time Log Shipping

### 5.1 Sending Logs to Multiple Backends

```python
"""
Ship logs to 3 backends:
1. LangSmith (for traces + logs correlation)
2. PostgreSQL (for long-term storage, querying)
3. Datadog (optional, for advanced analytics)
"""

import structlog
from datetime import datetime
import asyncio

class LogAggregator:
    """Routes logs to multiple backends"""
    
    def __init__(self):
        self.langsmith_client = Client()  # LangSmith
        self.pg_pool = Database("logs_db")  # PostgreSQL
        self.datadog_api = DatadogAPI()  # Optional
    
    async def log(self, log_entry: dict):
        """
        Ship log to all backends
        """
        
        # 1. LangSmith: For request tracing
        if log_entry.get("trace_id"):
            await self.langsmith_client.log_trace_event(
                trace_id=log_entry["trace_id"],
                span_id=log_entry["span_id"],
                message=log_entry["message"],
                metadata={k: v for k, v in log_entry.items() 
                         if k not in ["trace_id", "span_id", "message"]}
            )
        
        # 2. PostgreSQL: For querying & long-term storage
        await self.pg_pool.insert("logs", {
            "trace_id": log_entry.get("trace_id"),
            "request_id": log_entry.get("request_id"),
            "user_id": log_entry.get("user_id"),
            "level": log_entry["level"],
            "message": log_entry["message"],
            "context": json.dumps(log_entry.get("context", {})),
            "timestamp": datetime.fromisoformat(log_entry["timestamp"]),
            "created_at": datetime.utcnow()
        })
        
        # 3. Datadog: For advanced analytics (optional)
        if self.datadog_api.enabled:
            await self.datadog_api.log(log_entry)
    
    async def query_logs(self, filter_dict: dict):
        """Query logs from PostgreSQL"""
        query = "SELECT * FROM logs WHERE 1=1"
        params = []
        
        for key, value in filter_dict.items():
            query += f" AND {key} = %s"
            params.append(value)
        
        return await self.pg_pool.query(query, params)

# Hook into structlog
aggregator = LogAggregator()

async def async_log_handler(logger, method_name, event_dict):
    """Fire-and-forget logging to all backends"""
    asyncio.create_task(aggregator.log(event_dict))
    return event_dict

structlog.configure(
    processors=[
        # ... other processors ...
        async_log_handler
    ]
)
```

---

## Part 6: Metrics Collection

### 6.1 Key Metrics to Track

```python
"""
Track metrics across all layers
Prometheus-compatible format
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# COUNTERS: Cumulative values
requests_total = Counter(
    'rag_requests_total',
    'Total requests processed',
    ['layer', 'status']  # layer="ingestion", status="success"/"error"
)

errors_total = Counter(
    'rag_errors_total',
    'Total errors by type',
    ['error_type', 'layer']
)

# GAUGES: Current values
active_queries = Gauge(
    'rag_active_queries',
    'Currently processing queries'
)

cache_size_bytes = Gauge(
    'rag_cache_size_bytes',
    'Current cache size'
)

# HISTOGRAMS: Distributions
request_latency_ms = Histogram(
    'rag_request_latency_ms',
    'Request latency in milliseconds',
    ['operation']  # operation="search", "generate", "evaluate"
)

token_usage = Histogram(
    'rag_token_usage',
    'Tokens used per request',
    ['model']
)

# Usage in code
def search(query: str) -> List[str]:
    start = time.time()
    active_queries.inc()
    
    try:
        results = hybrid_search(query)
        latency = (time.time() - start) * 1000
        
        request_latency_ms.labels(operation="search").observe(latency)
        requests_total.labels(layer="retrieval", status="success").inc()
        
        return results
        
    except Exception as e:
        errors_total.labels(error_type=type(e).__name__, layer="retrieval").inc()
        raise
        
    finally:
        active_queries.dec()
```

### 6.2 Prometheus Scraping

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'rag_system'
    static_configs:
      - targets: ['localhost:8000']  # Your FastAPI app
    metrics_path: '/metrics'
```

---

## Part 7: Dashboards & Alerts

### 7.1 Grafana Dashboard Queries

```javascript
/*
Real-time dashboard for RAG system
*/

// Query 1: RAGAS Score Over Time
SELECT
  timestamp,
  ragas_score
FROM logs
WHERE logger = 'rag.evaluation'
  AND level = 'INFO'
  AND JSON_EXTRACT(context, '$.metric') = 'ragas_score'
ORDER BY timestamp DESC
LIMIT 1000

// Query 2: Error Rate by Layer
SELECT
  extract(hour from timestamp) as hour,
  COUNT(*) as total_requests,
  SUM(CASE WHEN level = 'ERROR' THEN 1 ELSE 0 END) as errors,
  (SUM(CASE WHEN level = 'ERROR' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as error_rate
FROM logs
WHERE timestamp > now() - INTERVAL '24 hours'
GROUP BY hour

// Query 3: Latency Percentiles
SELECT
  operation,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) as p50,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99,
  MAX(latency_ms) as max
FROM request_metrics
WHERE timestamp > now() - INTERVAL '1 hour'
GROUP BY operation
```

### 7.2 Alert Rules

```yaml
# alerts.yaml
groups:
  - name: rag_alerts
    rules:
      # Alert 1: High Error Rate
      - alert: HighErrorRate
        expr: (errors_total / requests_total) > 0.05  # 5% error rate
        for: 5m
        annotations:
          summary: "Error rate > 5%"
          description: "{{ $value }}% of requests are failing"
      
      # Alert 2: High Latency
      - alert: HighLatency
        expr: rag_request_latency_ms{quantile="0.95"} > 2000  # 2 seconds
        for: 10m
        annotations:
          summary: "P95 latency > 2 seconds"
          description: "95th percentile latency is {{ $value }}ms"
      
      # Alert 3: High Hallucination Rate
      - alert: HighHallucinationRate
        expr: (hallucinated_claims / total_claims) > 0.1  # 10%
        for: 30m
        annotations:
          summary: "Hallucination rate > 10%"
          action: "Review generation prompts"
      
      # Alert 4: Cache Miss Rate
      - alert: HighCacheMissRate
        expr: (cache_misses / (cache_hits + cache_misses)) > 0.8
        for: 15m
        annotations:
          summary: "Cache miss rate > 80%"
          action: "Increase cache size or TTL"
```

---

## Part 8: Querying Logs Efficiently

### 8.1 Common Query Patterns

```python
"""
Query logs from PostgreSQL for debugging
"""

# Query 1: Find all errors for a user
def get_user_errors(user_id: str, hours: int = 24):
    return db.query("""
        SELECT
          timestamp,
          level,
          message,
          trace_id,
          JSON_EXTRACT(context, '$.error') as error
        FROM logs
        WHERE user_id = %s
          AND level IN ('ERROR', 'CRITICAL')
          AND timestamp > now() - INTERVAL '%s hours'
        ORDER BY timestamp DESC
    """, (user_id, hours))

# Query 2: Trace full request lifecycle
def get_full_trace(trace_id: str):
    return db.query("""
        SELECT
          timestamp,
          logger,
          level,
          message,
          span_id,
          duration_ms,
          JSON_EXTRACT(context, '$.status') as status
        FROM logs
        WHERE trace_id = %s
        ORDER BY timestamp ASC
    """, (trace_id,))

# Query 3: Find slow queries
def get_slow_queries(threshold_ms: int = 5000):
    return db.query("""
        SELECT
          timestamp,
          user_id,
          trace_id,
          JSON_EXTRACT(context, '$.query') as query,
          duration_ms
        FROM logs
        WHERE logger = 'rag.generation'
          AND duration_ms > %s
          AND timestamp > now() - INTERVAL '7 days'
        ORDER BY duration_ms DESC
        LIMIT 100
    """, (threshold_ms,))

# Query 4: Correlation analysis
def get_correlated_events(start_time: str, end_time: str):
    """Find all events that happened together"""
    return db.query("""
        SELECT
          logger,
          level,
          COUNT(*) as count,
          AVG(duration_ms) as avg_duration
        FROM logs
        WHERE timestamp BETWEEN %s AND %s
        GROUP BY logger, level
        ORDER BY count DESC
    """, (start_time, end_time))
```

---

## Part 9: Log Retention & Archival

### 9.1 Data Retention Policy

```python
"""
Manage log retention to balance storage costs and queryability
"""

class LogRetentionPolicy:
    """
    Tiered retention:
    - Hot (7 days): Full logs, indexed, fast queries
    - Warm (30 days): Sampled logs, slower queries
    - Cold (90+ days): Archive, rarely accessed
    """
    
    HOT_RETENTION_DAYS = 7
    WARM_RETENTION_DAYS = 30
    COLD_RETENTION_DAYS = 90
    
    @staticmethod
    async def apply_retention():
        """Run daily to manage log lifecycle"""
        
        # Hot: Keep recent logs fully
        # (stays in PostgreSQL)
        
        # Warm: Compress and sample
        old_logs = await db.query("""
            SELECT * FROM logs
            WHERE created_at < now() - INTERVAL '%s days'
              AND created_at > now() - INTERVAL '%s days'
        """ % (LogRetentionPolicy.HOT_RETENTION_DAYS, 
               LogRetentionPolicy.WARM_RETENTION_DAYS))
        
        # Sample: Keep 10% of logs (errors at 100%)
        sampled = [
            log for log in old_logs
            if log['level'] == 'ERROR' or random.random() < 0.1
        ]
        
        # Move sampled to cold storage
        await move_to_s3(sampled, prefix="warm/")
        
        # Cold: Archive old logs to S3
        very_old = await db.query("""
            SELECT * FROM logs
            WHERE created_at < now() - INTERVAL '%s days'
        """ % LogRetentionPolicy.WARM_RETENTION_DAYS)
        
        await move_to_s3(very_old, prefix="cold/")
        await db.delete_logs_before(LogRetentionPolicy.WARM_RETENTION_DAYS)

async def move_to_s3(logs: List[Dict], prefix: str):
    """Archive logs to S3"""
    s3 = boto3.client('s3')
    key = f"logs/{prefix}{datetime.now().isoformat()}.jsonl"
    
    # Write as JSONL (one JSON per line, compressible)
    content = "\n".join(json.dumps(log) for log in logs)
    
    s3.put_object(
        Bucket='rag-logs-archive',
        Key=key,
        Body=gzip.compress(content.encode()),
        ContentEncoding='gzip'
    )
    
    logger.info("logs_archived", count=len(logs), location=key)
```

---

## Part 10: Integration Example: End-to-End Tracing

```python
"""
Complete example: One query traced through entire system
"""

from fastapi import FastAPI, Request
import structlog

app = FastAPI()
logger = structlog.get_logger("rag.api")

@app.post("/query")
@traceable(name="api_query")
async def query_handler(request: Request, query: str, user_id: str):
    """
    End-to-end request: Shows all layers logging with trace IDs
    """
    
    # Step 1: API receives request
    trace_id = str(uuid4())
    logger.info("api_request_received", 
                query=query, trace_id=trace_id)
    
    # Set trace context for all downstream operations
    trace_id_var.set(trace_id)
    user_id_var.set(user_id)
    
    # Step 2: Retrieve context
    logger.info("retrieval_starting")
    
    retrieved_chunks = await retrieve(query)
    
    logger.info("retrieval_complete",
                chunks_count=len(retrieved_chunks),
                latency_ms=retrieval_latency)
    
    # Step 3: Generate response
    logger.info("generation_starting")
    
    response = await generate(query, retrieved_chunks)
    
    logger.info("generation_complete",
                tokens_used=response.tokens,
                cost_usd=response.cost)
    
    # Step 4: Evaluate quality
    logger.info("evaluation_starting")
    
    evaluation = await evaluate(query, response, retrieved_chunks)
    
    logger.info("evaluation_complete",
                ragas_score=evaluation.score,
                quality_tier=evaluation.tier)
    
    # Final log
    logger.info("request_complete",
                total_latency_ms=total_latency,
                cost_usd=total_cost,
                status="success",
                trace_id=trace_id  # Include for easy lookup
    )
    
    return {
        "response": response.text,
        "trace_id": trace_id,  # Return to user for debugging
        "quality": evaluation.score
    }

# Result: LangSmith shows:
# 1. Parent span: api_query
# 2. Child span: retrieve
# 3. Child span: generate
# 4. Child span: evaluate
# All with same trace_id
# Each with logs, timing, cost
# Fully queryable and analyzable
```

---

## Part 11: Configuration

```yaml
# logging_config.yaml
logging:
  # JSON Structured Logging
  structured_logging:
    enabled: true
    format: "json"
    level: "INFO"  # DEBUG in dev, INFO in prod
    
    # Backends
    backends:
      langsmith:
        enabled: true
        api_key: ${LANGSMITH_API_KEY}
        project: "rag_system"
      
      postgresql:
        enabled: true
        connection_string: ${DATABASE_URL}
        table: "logs"
        batch_size: 100
        flush_interval_seconds: 5
      
      datadog:
        enabled: false  # Optional
        api_key: ${DATADOG_API_KEY}
        site: "datadoghq.com"
  
  # Metrics (Prometheus)
  metrics:
    enabled: true
    port: 9090
    scrape_interval: 15s
  
  # Log Retention
  retention:
    hot_days: 7
    warm_days: 30
    cold_days: 90
    archive_to_s3: true
    s3_bucket: "rag-logs-archive"
  
  # Alerting
  alerting:
    enabled: true
    error_rate_threshold: 0.05  # 5%
    latency_p95_threshold_ms: 2000
    hallucination_rate_threshold: 0.10
    alert_channels: ["slack", "email"]
    slack_webhook: ${SLACK_WEBHOOK}
```

---

## Part 12: Logging Framework as Nervous System Summary

Your logging framework **perfectly fits** because:

✅ **Comprehensive**: Every layer instruments (ingestion→evaluation)  
✅ **Correlated**: Trace ID links all events for one request  
✅ **Observable**: 3 pillars (logs, metrics, traces) tell complete story  
✅ **Queryable**: Structured JSON enables powerful debugging  
✅ **Real-time**: LangSmith shows issues as they happen  
✅ **Cost-aware**: Track spending per component  
✅ **Multi-tenant**: User/tenant isolation built-in  
✅ **Production-ready**: Retention policies, archival, alerts  

**The nervous system works because**:
- Signals (logs) flow from every layer to central monitoring
- Trace IDs act like "blood" carrying context through system
- Metrics aggregate signals for health monitoring
- Dashboards give real-time visibility
- Alerts notify when something breaks
- Root cause analysis enabled by trace correlation

---

## Next Implementation Steps

1. **Set up structlog** (30 min)
   - Configure JSON logging
   - Add context variables
   
2. **Integrate LangSmith** (1 hour)
   - @traceable decorators on key functions
   - Trace ID propagation
   
3. **Set up Prometheus** (1 hour)
   - Define key metrics
   - Configure scraping
   
4. **Create Grafana dashboards** (2 hours)
   - Real-time RAGAS score
   - Error rates by layer
   - Latency percentiles
   
5. **Configure alerts** (1 hour)
   - Error rate > 5%
   - Latency p95 > 2s
   - Hallucination rate > 10%
   
6. **Set up PostgreSQL logging** (1 hour)
   - Log table creation
   - Retention policies

**Total**: 6-7 hours to full observability 🎉
