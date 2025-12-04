# Logging Framework Visual Architecture Guide

## Complete Data Flow Diagram (ASCII + Description)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          RAG SYSTEM LOGGING FRAMEWORK                              │
│                         (The Nervous System in Action)                             │
└─────────────────────────────────────────────────────────────────────────────────────┘

LAYER 1: EVENT SOURCES (RAG Component Instrumentation)
╔════════════════════════════════════════════════════════════════════════════════════╗
│                                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │  INGESTION      │  │  RETRIEVAL      │  │  GENERATION     │  │ EVALUATION   │  │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤  ├──────────────┤  │
│  │ File upload     │  │ Query received  │  │ Prompt assembly │  │ Score compute│  │
│  │ Parsing         │  │ Hybrid search   │  │ API call        │  │ Metrics eval │  │
│  │ Chunking        │  │ Reranking       │  │ Token usage     │  │ Quality tier │  │
│  │ Embedding       │  │ Caching check   │  │ Streaming       │  │ Issue detect │  │
│  │ Storage         │  │                 │  │ Completion      │  │              │  │
│  └──────┬──────────┘  └──────┬──────────┘  └────────┬────────┘  └──────┬───────┘  │
│         │                    │                      │                   │          │
│         │ emit event         │ emit event           │ emit event        │ emit event│
│         │ with trace_id      │ with trace_id        │ with trace_id     │ with trace│
│         │                    │                      │                   │          │
└────────┬────────────────────┬──────────────────────┬───────────────────┬──────────┘
         │                    │                      │                   │

LAYER 2: STRUCTURED JSON LOGGING (With Context Propagation)
─────────────────────────────────────────────────────────────────────────────────────
         │                    │                      │                   │
         │                    ▼                      │                   │
         │                    ▼                      ▼                   ▼
         └────────────────────────────────────────────────────────────────────┐
                                                                              │
                    ┌───────────────────────────────────────┐               │
                    │  STRUCTURED JSON LOG CREATION         │               │
                    ├───────────────────────────────────────┤               │
                    │ {                                     │               │
                    │   "timestamp": "2025-12-03T22:45:30", │               │
                    │   "trace_id": "550e8400-...",         │◄──┬──────────┘
                    │   "span_id": "f4dfc083-...",          │   │
                    │   "user_id": "user-123",              │   │
                    │   "level": "INFO",                    │   │ Context Variables
                    │   "message": "chunks_created",        │   │ (From contextvars)
                    │   "context": {                        │   │
                    │     "chunk_count": 42,                │   │
                    │     "file_size_bytes": 3145728        │   │
                    │   },                                  │   │
                    │   "metrics": {                        │   │
                    │     "duration_ms": 1250,              │   │
                    │     "cost_usd": 0.012                 │   │
                    │   }                                   │   │
                    │ }                                     │   │
                    └─────────────────────────┬─────────────┘   │
                                              │                 │
                                              │ One JSON event  │
                                              │ Ready to ship   │
                                              │                 │
                                              ▼                 │

LAYER 3: ASYNC LOG AGGREGATOR (Multi-Backend Shipping)
─────────────────────────────────────────────────────────────────────────────────────
                                              │
                                    ┌─────────▼──────────┐
                                    │  LOG AGGREGATOR    │
                                    │  (Fire & Forget)   │
                                    └─────────┬──────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼

LAYER 4: MULTI-BACKEND STORAGE & ROUTING
─────────────────────────────────────────────────────────────────────────────────────

    ┌──────────────────────┐      ┌──────────────────────┐      ┌─────────────────┐
    │   LANGSMITH          │      │   POSTGRESQL         │      │  PROMETHEUS     │
    │   (Distributed Trace)│      │   (Event Storage)    │      │  (Metrics Store)│
    ├──────────────────────┤      ├──────────────────────┤      ├─────────────────┤
    │                      │      │                      │      │                 │
    │ ✓ Nested spans      │      │ ✓ JSONB storage      │      │ ✓ Time-series   │
    │ ✓ Waterfall view    │      │ ✓ Full-text search   │      │ ✓ Aggregation   │
    │ ✓ Visual traces     │      │ ✓ Queryable logs     │      │ ✓ High cardinty │
    │ ✓ Cost tracking     │      │ ✓ Indexed by trace   │      │ ✓ Scrape API    │
    │ ✓ 30 day retention  │      │ ✓ 7 day hot (7 day)  │      │ ✓ 15 day keep   │
    │                      │      │ ✓ 30 day warm (sampl)│      │                 │
    │ 🔗 trace_id linking │      │ 🔗 trace_id indexing│      │ 🔗 trace_id tag │
    │                      │      │                      │      │                 │
    └──────────┬───────────┘      └──────────┬───────────┘      └────────┬────────┘
               │ <50ms            │ <100ms   │ <200ms           │
               │ Native           │ Async    │ Batched          │
               │ Integration      │ Batched  │                  │
               │                  │          │                  │

LAYER 5: CORRELATION & AGGREGATION (The Magic Happens)
─────────────────────────────────────────────────────────────────────────────────────

                            ┌────────────────────────────────┐
                            │   TRACE ID = Universal Key     │
                            │   All 3 backends keyed by it   │
                            │   Query any backend, find all  │
                            └────────┬───────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
        ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐
        │ LangSmith Trace │  │ PostgreSQL Logs  │  │ Prometheus   │
        │                 │  │                  │  │ Metrics      │
        │ trace_id: abc   │  │ SELECT FROM logs │  │ QUERY: ...   │
        │   ├─ span 1     │  │ WHERE trace_id   │  │ {            │
        │   │  └─ span 2  │  │ = 'abc' (500ms)  │  │   latency_ms │
        │   └─ span 3     │  │                  │  │   error_rate │
        │                 │  │ 10 log entries   │  │   tokens_used│
        │ waterfall view  │  │ with full context│  │ }            │
        │ shows: 2.5s     │  │                  │  │              │
        │ for entire req  │  │                  │  │ last hour's  │
        │                 │  │                  │  │ aggregates   │
        └─────────────────┘  └──────────────────┘  └──────────────┘

LAYER 6: CONSUMER TOOLS & DASHBOARDS (Actionable Insights)
─────────────────────────────────────────────────────────────────────────────────────

    ┌───────────────────┐    ┌────────────────────┐    ┌──────────────────┐
    │  GRAFANA          │    │  LOG QUERY TOOL    │    │  ALERTING        │
    │  (Visualization)  │    │  (Debugging)       │    │  (Notifications) │
    ├───────────────────┤    ├────────────────────┤    ├──────────────────┤
    │                   │    │                    │    │                  │
    │ ✓ Real-time dash  │    │ ✓ Find by trace_id │    │ ✓ Error rate > 5%│
    │ ✓ Latency trends  │    │ ✓ Find by user_id  │    │ ✓ Latency > 2s   │
    │ ✓ Error spikes    │    │ ✓ Time range query │    │ ✓ Halluc > 10%   │
    │ ✓ RAGAS scores    │    │ ✓ Full-text search │    │ ✓ Cache miss > 80│
    │ ✓ Cost breakdown  │    │ ✓ Stack traces     │    │ ✓ To: Slack/Mail │
    │ ✓ Histograms      │    │                    │    │                  │
    │                   │    │ Query response:    │    │ Example:         │
    │ Example insight:  │    │ {                  │    │ "@team Error     │
    │ "RAGAS degraded"  │    │   logs: [          │    │ spiked to 8.3%   │
    │ after deploy      │    │     {timestamp}    │    │ (threshold: 5%)  │
    │ at 21:33          │    │     {message}      │    │                  │
    │ Peak: 0.62        │    │     {error}        │    │ Trace ID: xyz    │
    │ Now: 0.48         │    │   ]                │    │ Action: rollback"│
    │                   │    │ }                  │    │                  │
    └─────────┬─────────┘    └────────┬───────────┘    └──────────┬───────┘
              │                       │                           │
              │ Visual Pattern        │ Detailed Debugging        │ Reactive
              │ Recognition           │ Forensics                 │ Response


LAYER 7: FEEDBACK LOOPS (Continuous Improvement)
─────────────────────────────────────────────────────────────────────────────────────

    Alerts trigger        Logs reveal          Dashboards show
    something wrong       root cause           improvement
        │                    │                      │
        ├─ Too slow?        ├─ OOM in embedding   ├─ Latency ↓ 40%
        ├─ Too errors?      ├─ API rate limit     ├─ Errors ↓ 80%
        ├─ Low quality?     ├─ Bad chunk quality  ├─ Quality ↑ 15%
        │                   │                     │
        └─────────────┬─────┴─────────────────────┘
                      │
                 FIX IDENTIFIED:
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    Code Change  Config Change  Prompt Tuning
         │            │            │
         └────────────┴────────────┘
                      │
              Deploy & Monitor
                      │
              Metrics improve
              (Verified by logs!)


═════════════════════════════════════════════════════════════════════════════════════════

REAL EXAMPLE: Following One Request Through the System

User uploads "report.pdf"
     │
     ├─ Trace ID generated: "550e8400-e29b-41d4-a716-446655440000"
     │
     ├──→ INGESTION logs with trace_id:
     │    ├─ "file_upload_started" (1 log entry)
     │    ├─ "parsing_complete" (1 log entry)
     │    ├─ "chunking_complete" (1 log entry)
     │    ├─ "embedding_complete" (1 log entry)
     │    └─ "storage_complete" (1 log entry)
     │
     ├──→ All 5 logs ship to:
     │    ├─ PostgreSQL (queryable, full details)
     │    ├─ LangSmith (visual trace with timing)
     │    └─ Prometheus (metrics: duration, cost)
     │
     ├──→ Later: Developer investigates latency
     │    ├─ Check Grafana: "Ingestion slower than usual"
     │    ├─ Get trace_id from dashboard: "550e8400-..."
     │    ├─ Query PostgreSQL: SELECT * FROM logs WHERE trace_id = '550e8400-...'
     │    ├─ See logs: chunking took 3 seconds (slow!)
     │    ├─ Check LangSmith: Visual shows embedding span taking 2.8s
     │    ├─ Root cause: OpenAI API slow today
     │    ├─ Action: Implement retry logic with exponential backoff
     │    └─ Deploy fix
     │
     └──→ Post-fix: Metrics show:
          ├─ Ingestion latency ↓ 40%
          ├─ Error rate ↓ from 2.3% to 0.8%
          └─ All confirmed by logging data!

═════════════════════════════════════════════════════════════════════════════════════════
```

---

## Key Integration Points

### 1. Request Entry Point (API Middleware)
```
FastAPI request arrives
    ↓
Middleware extracts trace_id from header
    ↓
Sets contextvars: trace_id, user_id, request_id
    ↓
All downstream code sees these automatically
    ↓
Every log automatically includes them
```

### 2. Component Instrumentation
```
@traceable decorator on function
    ↓
LangSmith creates span
    ↓
Function logs events with context
    ↓
Trace ID automatically included
    ↓
Function returns
    ↓
LangSmith records timing
```

### 3. Multi-Backend Routing
```
Log entry created
    ↓
Aggregator queues it
    ↓
Background worker batches logs
    ↓
Ships simultaneously to:
    ├─ PostgreSQL (100ms)
    ├─ LangSmith (50ms)
    └─ Prometheus (200ms)
```

### 4. Query & Analysis
```
"Why is this slow?"
    ↓
Click dashboard spike
    ↓
Get trace_id from details
    ↓
Query PostgreSQL with trace_id
    ↓
See all events in order
    ↓
Identify bottleneck
    ↓
Fix implemented
    ↓
Monitor improvement in dashboard
```

---

## Performance Characteristics

### Logging Overhead
```
Operation: Log emission
├─ Create JSON: <0.1ms
├─ Queue async: <0.01ms
├─ Ship to PostgreSQL: <100ms (async, doesn't block)
├─ Ship to LangSmith: <50ms (native integration)
└─ Ship to Prometheus: <200ms (batched)

Total app impact: <0.5ms per request (async)
Storage overhead: ~1KB per log entry
```

### Query Performance
```
PostgreSQL queries:
├─ By trace_id: <50ms (indexed)
├─ By user_id: <100ms (indexed)
├─ By time range: <500ms (depends on range)
├─ Full-text search: <1000ms (depends on terms)

LangSmith queries:
├─ Get trace: <50ms
├─ Get span: <20ms

Prometheus queries:
├─ Last hour: <100ms
├─ Last 7 days: <500ms
```

---

## What Makes This Production-Grade

✅ **Minimal overhead**: Async shipping, batching  
✅ **High reliability**: 3 backends, no single point of failure  
✅ **Queryable**: Indexed PostgreSQL, full-text search  
✅ **Traceable**: Trace IDs link everything  
✅ **Correlated**: One ID unifies logs, metrics, traces  
✅ **Observable**: Real-time dashboards + historical analysis  
✅ **Cost-effective**: $0.008-0.013 per query  
✅ **Scalable**: Handles 10k+ requests/month  
✅ **Debuggable**: Root cause analysis in seconds  
✅ **Improvable**: Data-driven optimization  

---

## Files Generated

This framework consists of:
- **09_Logging_Framework_Design.md** - Complete architecture (56KB)
- **10_Logging_Implementation.md** - Production code (50KB)
- **LOGGING_QUICK_REFERENCE.md** - Quick guide (20KB)
- **LOGGING_VISUAL_GUIDE.md** - This file with diagrams

**Total documentation**: 150+ KB of production-ready content

Start with this guide, reference the detailed design docs while building. You've got everything needed! 🎉
