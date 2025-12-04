# Logging Framework Summary - Quick Reference Guide

## Your Logging Framework: The System's Nervous System

### What You're Building

A **production-grade observability system** that enables you to:

1. **See everything happening** - Every operation instrumented
2. **Trace requests end-to-end** - Follow one query through all layers
3. **Find problems instantly** - Root cause analysis in seconds
4. **Optimize continuously** - Data-driven improvements

---

## The Three Pillars (Interconnected)

### 📊 PILLAR 1: Logs (Events & Context)
**What**: Structured JSON records of every event  
**Where**: PostgreSQL (queryable)  
**Retention**: 7-30 days (hot, then warm archive)  
**Format**: JSON with trace_id, span_id, user_id, context  
**Query**: "Find all errors for user-123 in last 24h"

### 📈 PILLAR 2: Metrics (Aggregated Signals)  
**What**: Counters, gauges, histograms from all layers  
**Where**: Prometheus (time-series DB)  
**Retention**: 15 days  
**Examples**: Request latency p95, error rate, token usage  
**Visualize**: Grafana dashboards (real-time + historical)

### 🔗 PILLAR 3: Traces (Request Flow)
**What**: Nested spans showing operation sequence  
**Where**: LangSmith (native, visual)  
**Retention**: 30 days  
**View**: Waterfall diagram showing each layer's contribution  
**Correlation**: Trace ID links all three pillars

---

## The Magic: Trace IDs Bridge Everything

```
One request = One trace ID flows through entire system
├─ PostgreSQL logs all have trace_id
├─ Prometheus metrics tagged with trace_id  
├─ LangSmith shows spans with trace_id
└─ Result: Click one error → see full request lifecycle
```

**Example Flow**:
1. Dashboard shows latency spike
2. Click spike → drill down to errors  
3. See error has trace_id = "abc123"
4. Query PostgreSQL: `WHERE trace_id = 'abc123'`
5. See logs: file upload → chunking → error during embedding
6. Found root cause: file too large, OOM error

---

## Architecture: From Components to Insight

```
┌─ INGESTION ─────┐
│ Upload file     │ → "file_upload_started" → logs with trace_id
└─────────────────┘
         ↓
┌─ PARSING ──────────┐
│ Read file          │ → "parsing_complete" → logs with trace_id
└────────────────────┘
         ↓
┌─ CHUNKING ─────────┐
│ Split into chunks  │ → "chunking_complete" → logs with trace_id
└────────────────────┘
         ↓
┌─ ENRICHMENT ──────┐
│ Add metadata       │ → "enrichment_complete" → logs with trace_id
└────────────────────┘
         ↓
┌─ EMBEDDING ────────┐
│ Create vectors     │ → "embedding_complete" → logs with trace_id
└────────────────────┘
         ↓
┌─ STORAGE ──────────┐
│ Save to Pinecone   │ → "storage_complete" → logs with trace_id
└────────────────────┘

All logs ship to:
├─ PostgreSQL (queryable)
├─ LangSmith (visual traces)
└─ Metrics (aggregation)

Unified view: "What happened to this request?"
```

---

## Key Components You'll Build

### 1. Structured JSON Logger (`structlog`)
```python
logger.info("event_name",
            trace_id="550e8400-...",  # Automatic
            user_id="user-123",       # Context variable
            duration_ms=1250,         # Metric
            status="success")         # Outcome
```
→ Outputs: `{"timestamp": "...", "level": "INFO", "message": "event_name", ...}`

### 2. Trace Context Manager
```python
with trace_span("file_parsing", trace_ctx):
    parse_file(...)  # Automatically timed and logged
```
→ Creates new span, logs timing, propagates trace_id

### 3. FastAPI Middleware
```python
@app.middleware
async def logging_middleware(request):
    trace_id = request.headers.get("X-Trace-ID", uuid4())
    trace_id_var.set(trace_id)
    # All downstream logs get this trace_id
```
→ Extracts/creates trace_id, sets context

### 4. Log Aggregator (Multi-backend)
```python
aggregator.log(event_dict)
# Automatically ships to:
# ├─ PostgreSQL
# ├─ LangSmith
# └─ Prometheus
```
→ Fire-and-forget async shipping to all backends

### 5. Query Tools
```python
debug_trace("550e8400-...")  # Get full request
find_errors("user-123")      # Find all issues for user
```
→ Human-friendly debugging tools

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Log shipping latency | <100ms | Async, batched |
| PostgreSQL query | <500ms | Indexed, JSONB support |
| LangSmith trace creation | <50ms | Native integration |
| Trace correlation | <10ms | In-memory operation |
| Storage overhead | <5% | Minimal impact on main app |

---

## Cost Estimation (10k requests/month)

| Component | Cost | Notes |
|-----------|------|-------|
| PostgreSQL logs | $50-70 | 7-day retention, indexed |
| Prometheus | $30-50 | 15-day retention |
| LangSmith | Free tier | 30-day retention |
| Storage/Archive | $5-10 | S3 for old logs |
| **Total** | **$85-130** | **$0.008-0.013/query** |

---

## What Gets Logged (By Layer)

### Ingestion Layer
- `file_upload_started` - File size, format, user
- `file_parsed` - Document count
- `chunks_created` - Count, avg size
- `enrichment_complete` - Metadata added
- `embedding_complete` - Token cost, API usage
- `storage_complete` - Pinecone IDs

### Retrieval Layer
- `search_query_received` - Query text
- `hybrid_search_executed` - Dense + sparse results
- `reranking_complete` - Final ranking scores
- `chunks_retrieved` - Count, relevance scores

### Generation Layer
- `generation_started` - Model, temperature
- `token_budget_allocated` - Total, query, context, response
- `streaming_started` - Connection established
- `generation_complete` - Tokens used, cost

### Evaluation Layer
- `evaluation_started` - Metrics to compute
- `ragas_score_computed` - Faithfulness, relevancy, etc.
- `quality_tier_assigned` - Good/fair/poor
- `evaluation_complete` - Actions triggered

### Memory Layer
- `history_retrieved` - Turn count, tokens
- `history_summarized` - Compression ratio
- `history_stored` - DB location

---

## Real-World Debugging Examples

### Example 1: "Why is my generation slow?"
```
Dashboard → Latency spike in generation layer
Click spike → Find trace_id "xyz"
Query: SELECT * FROM logs WHERE trace_id='xyz' ORDER BY timestamp
Result:
  22:45:30 generation_started (token_budget: 3500/128000)
  22:45:31 streaming_started
  22:45:35 generation_complete (latency: 5000ms)

Root cause: Streaming took 4 seconds (network issue)
Action: Increase chunk size or use mini model
```

### Example 2: "Why are errors spiking?"
```
Alert triggered: Error rate > 5%
Drill down → See pattern: All errors in retrieval layer
Query: SELECT error FROM logs WHERE level='ERROR' LIMIT 100
Result: All say "Pinecone connection timeout"

Root cause: Pinecone rate limit
Action: Add connection pooling, backoff strategy
```

### Example 3: "Why is one user having bad quality?"
```
Dashboard: RAGAS score for user-123 = 0.42 (red)
Click → See trace_id "abc"
Query: SELECT * FROM logs WHERE trace_id='abc'
Result: Retrieved chunks have low relevance scores

Root cause: Hybrid search weights misconfigured
Action: Tune BM25 weight, increase density threshold
```

---

## Implementation Checklist

### Week 1: Foundation
- [ ] Set up structlog with JSON output
- [ ] Create PostgreSQL logs table with indexes
- [ ] Set up Python context variables (trace_id, span_id, user_id)
- [ ] Create FastAPI logging middleware
- **Result**: Basic request logging working

### Week 2: Instrumentation
- [ ] Add @traceable decorators to key functions
- [ ] Create trace_span context managers
- [ ] Instrument all 6 layers with logging
- [ ] Set up async log aggregator
- **Result**: Full request tracing enabled

### Week 3: Aggregation & Visibility
- [ ] Set up Prometheus metrics
- [ ] Create Grafana dashboards
- [ ] Configure LangSmith integration
- [ ] Set up alerting rules
- **Result**: Real-time dashboards and alerts

### Week 4: Operations
- [ ] Create query debugging tools
- [ ] Set up log retention policies
- [ ] Document common queries
- [ ] Train team on using dashboards
- **Result**: Production-grade observability

---

## Key Dependencies

```python
# Core logging
structlog>=23.1.0
python-json-logger>=2.0.0

# Distributed tracing
langsmith>=0.0.40
langchain>=0.0.300

# Database
psycopg-pool>=3.0.0
sqlalchemy>=2.0.0

# Metrics
prometheus-client>=0.18.0
pyexpat>=3.18.0

# Optional: Advanced analytics
datadog>=0.45.0
```

---

## Files to Create

1. **`config/logging_config.py`** - Structlog setup
2. **`core/tracing.py`** - TraceContext, trace_span
3. **`core/log_aggregator.py`** - Multi-backend shipping
4. **`api/logging_middleware.py`** - FastAPI middleware
5. **`migrations/create_logs_table.sql`** - Database schema
6. **`tools/log_query.py`** - Debugging queries
7. **`prometheus.yml`** - Metrics scraping config
8. **`grafana_dashboards/rag_dashboard.json`** - Visualization

---

## Next Steps

1. **Start simple**: Just log to PostgreSQL first
2. **Add trace IDs**: Follow one request through system
3. **Add metrics**: Track performance signals
4. **Add dashboards**: Visualize in real-time
5. **Add alerting**: Notify on issues
6. **Optimize**: Based on data, improve continuously

The nervous system enables everything else! 🧠

---

## Questions to Ask While Building

✓ Can I see what happened to this request?  
✓ Can I trace where it broke?  
✓ Can I find all similar failures?  
✓ Can I see performance trends?  
✓ Can I correlate errors with code changes?  
✓ Can I measure cost per operation?  

All answerable with this framework! ✅
