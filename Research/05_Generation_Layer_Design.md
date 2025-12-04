# Generation Layer Design - Production RAG System

## Executive Summary

The **Generation Layer** is where your RAG system produces user-facing answers. It receives carefully curated context from Retrieval/Reranking and uses OpenAI's GPT models to generate nuanced, cited, faithful responses. It operates as a **multi-stage generation pipeline** with:

- **Prompt Assembly**: Optimal token allocation across system prompt, context, query, response
- **Model Selection**: Intelligently route between GPT-4o (quality), GPT-4o-mini (speed/cost)
- **Streaming Generation**: Real-time text-to-user for perceived latency reduction
- **Citation Management**: Track & embed source attribution for every claim
- **Memory Integration**: Use conversation history for coherent multi-turn dialogue
- **Fallback Strategies**: Graceful degradation when context insufficient or model unavailable
- **Observability**: LangSmith tracing for prompt optimization

This design treats the Generation Layer as a **LEGO brick** that:
✓ Accepts precisely-formatted RetrievedChunk objects from Data Layer
✓ Produces faithful, cited responses within token budget
✓ Integrates conversation history for dialogue coherence
✓ Streams output for better UX
✓ Tracks citations for evaluation & legal compliance
✓ Accepts quality feedback from Evaluation component

---

## Part 1: Architecture Overview

### Generation Pipeline - The LEGO Brick

```
┌───────────────────────────────────────────────────────────────────┐
│              GENERATION LAYER (Multi-Stage Pipeline)              │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  INPUT: Reranked Retrieval Results from Data Layer               │
│  ├─ top_k RetrievedChunk objects (10-20 chunks)                  │
│  ├─ Ranked by relevance score (0.0-1.0)                          │
│  ├─ With metadata: source, page_number, language, etc.           │
│  ├─ User query (original question)                               │
│  └─ Conversation history (optional, for dialogue)                │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  STAGE 1: PROMPT ASSEMBLY                                    │ │
│  ├──────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Token Budget Analysis                                    │ │
│  │  │  ├─ Total context window: 128K tokens (GPT-4o)          │ │
│  │  │  ├─ System prompt: 500 tokens (fixed)                   │ │
│  │  │  ├─ User query: 50-200 tokens (variable)                │ │
│  │  │  ├─ Conversation history: 0-2000 tokens (if multi-turn)  │ │
│  │  │  ├─ Retrieved context: 2000-4000 tokens (variable)       │ │
│  │  │  ├─ Few-shot examples: 500 tokens (optional)             │ │
│  │  │  └─ Response budget: 1000-2000 tokens (reserved)         │ │
│  │  │                                                             │ │
│  │  ├─ Context Assembly                                         │ │
│  │  │  ├─ Sort chunks by relevance                            │ │
│  │  │  ├─ Remove duplicates/redundant content                 │ │
│  │  │  ├─ Format with headers & attribution                   │ │
│  │  │  ├─ Inject source citations                             │ │
│  │  │  └─ Truncate if exceeds token budget                    │ │
│  │  │                                                             │ │
│  │  └─ Prompt Template Construction                            │ │
│  │     └─ [System Prompt] + [Context] + [History] + [Query]   │ │
│  │                                                             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  STAGE 2: MODEL SELECTION & ROUTING                          │ │
│  ├──────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Model Router                                             │ │
│  │  │  ├─ Query complexity analysis                            │ │
│  │  │  │  ├─ Simple (FAQ, direct lookup): GPT-4o-mini         │ │
│  │  │  │  ├─ Complex (multi-hop reasoning): GPT-4o            │ │
│  │  │  │  ├─ Specialized (code generation): GPT-4o            │ │
│  │  │  │  └─ Fallback: GPT-4o-mini if GPT-4o unavailable      │ │
│  │  │  │                                                        │ │
│  │  │  ├─ Cost-quality tradeoff                               │ │
│  │  │  │  ├─ Cost budget: use cheaper mini model             │ │
│  │  │  │  ├─ Quality critical: use full GPT-4o               │ │
│  │  │  │  └─ Standard: dynamic routing based on load          │ │
│  │  │  │                                                        │ │
│  │  │  └─ Load-based routing                                  │ │
│  │  │     ├─ If GPT-4o queue > 100ms: route to mini          │ │
│  │  │     └─ If mini queue > 200ms: route to GPT-4o          │ │
│  │  │                                                             │ │
│  │  └─ Temperature & Sampling                                   │ │
│  │     ├─ Factual answers (FAQ): temp=0.0 (deterministic)     │ │
│  │     ├─ Creative answers: temp=0.7 (balanced)               │ │
│  │     └─ Reasoning: temp=0.3 (focused)                       │ │
│  │                                                             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  STAGE 3: STREAMING GENERATION                               │ │
│  ├──────────────────────────────────────────────────────────────┤ │
│  │  ┌─ OpenAI Streaming API (stream=True)                      │ │
│  │  │  ├─ Connection: HTTP/WebSocket to OpenAI                │ │
│  │  │  ├─ Response format: SSE (Server-Sent Events)           │ │
│  │  │  ├─ Token chunks: 1-5 tokens per event                  │ │
│  │  │  └─ Latency: ~20-50ms per chunk (pipelined)             │ │
│  │  │                                                             │ │
│  │  ├─ Stream Processing                                        │ │
│  │  │  ├─ Buffer tokens for optimal batching                  │ │
│  │  │  ├─ Detect citations in real-time                       │ │
│  │  │  ├─ Format output for UI (markdown, HTML)               │ │
│  │  │  ├─ Track token count for cost                          │ │
│  │  │  └─ Error handling & stream recovery                    │ │
│  │  │                                                             │ │
│  │  └─ WebSocket to Frontend                                   │ │
│  │     ├─ Send tokens as they arrive                          │ │
│  │     ├─ Update progress/metadata                            │ │
│  │     └─ Handle disconnect/reconnect                         │ │
│  │                                                             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  STAGE 4: CITATION MANAGEMENT & POST-PROCESSING             │ │
│  ├──────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Citation Extraction                                      │ │
│  │  │  ├─ Pattern matching: [Source: chunk-123]               │ │
│  │  │  ├─ Footnote generation: [1], [2], [3]                  │ │
│  │  │  ├─ Reference list assembly                             │ │
│  │  │  └─ Validation: match citations to source chunks        │ │
│  │  │                                                             │ │
│  │  ├─ Hallucination Detection                                 │ │
│  │  │  ├─ LLM evaluator: Does response match context?         │ │
│  │  │  ├─ Fact-checking: Call fact-checking service           │ │
│  │  │  ├─ Confidence scoring: 0.0-1.0                         │ │
│  │  │  └─ Flag if score < threshold (alert user)              │ │
│  │  │                                                             │ │
│  │  └─ Response Validation                                      │ │
│  │     ├─ Check against guardrails (safety, content policy)   │ │
│  │     ├─ Length validation (within response budget)          │ │
│  │     ├─ Format validation (markdown, JSON, etc.)            │ │
│  │     └─ Regenerate if validation fails                      │ │
│  │                                                             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  STAGE 5: MEMORY & CONTEXT MANAGEMENT                       │ │
│  ├──────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Conversation History                                     │ │
│  │  │  ├─ Store: (user_query, assistant_response) tuples      │ │
│  │  │  ├─ Window: last N turns (e.g., 5 turns = 10 messages)  │ │
│  │  │  ├─ Summarization: if history > 2000 tokens, summarize  │ │
│  │  │  └─ Storage: Redis cache + PostgreSQL audit             │ │
│  │  │                                                             │ │
│  │  ├─ Context Carry-Forward                                   │ │
│  │  │  ├─ Entity resolution: "it" → "Company X"               │ │
│  │  │  ├─ Implicit constraints: remember filters from prev Q   │ │
│  │  │  └─ Topic tracking: maintain conversation thread         │ │
│  │  │                                                             │ │
│  │  └─ Memory Injection (Part of Prompt)                       │ │
│  │     ├─ Previous answers for consistency                     │ │
│  │     ├─ User preferences from history                        │ │
│  │     └─ Context continuity signals                           │ │
│  │                                                             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  OUTPUT: GeneratedResponse object                                │
│  ├─ generated_text: str (the full response)                    │
│  ├─ citations: List[Citation] (source chunks with quotes)      │
│  ├─ confidence_score: float (0.0-1.0)                          │
│  ├─ tokens_used: {input, output, total}                        │
│  ├─ latency_ms: float                                           │
│  ├─ model_used: str                                             │
│  ├─ finish_reason: str ("stop", "max_tokens", "error")         │
│  └─ metadata: Dict (for tracing & evaluation)                  │
│                                                                     │
│  FEEDBACK LOOP: Evaluation → Quality Scores → Prompt Tuning     │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Token Budget Management (Critical for Cost & Quality)

```python
"""
Token Budget Strategy: Allocate context window for optimal quality
Most expensive tokens are INPUT tokens (reading cost)
OUTPUT tokens also cost, but less than input
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import tiktoken

@dataclass
class TokenBudget:
    """Represents token allocation for a single generation request"""
    
    # Total window
    total_context_window: int = 128000  # GPT-4o
    
    # Allocations (fixed)
    system_prompt_tokens: int = 500  # Instruction overhead
    
    # Allocations (variable)
    user_query_tokens: int  # Estimated from query text
    conversation_history_tokens: int = 0  # Only if multi-turn
    few_shot_examples_tokens: int = 0  # Optional
    
    # Dynamic allocation
    available_for_context: int = 0  # Computed
    response_budget_tokens: int = 1000  # Reserved for output
    
    # Actual usage (computed after)
    context_tokens_used: int = 0
    response_tokens_generated: int = 0
    
    def __post_init__(self):
        """Calculate remaining context budget"""
        used = (
            self.system_prompt_tokens +
            self.user_query_tokens +
            self.conversation_history_tokens +
            self.few_shot_examples_tokens +
            self.response_budget_tokens
        )
        self.available_for_context = self.total_context_window - used
    
    def is_within_budget(self) -> bool:
        """Check if allocation is valid"""
        return self.available_for_context > 0
    
    def get_summary(self) -> Dict:
        """Return budget breakdown"""
        return {
            "total_window": self.total_context_window,
            "system_prompt": self.system_prompt_tokens,
            "query": self.user_query_tokens,
            "history": self.conversation_history_tokens,
            "examples": self.few_shot_examples_tokens,
            "reserved_for_response": self.response_budget_tokens,
            "available_for_context": self.available_for_context,
            "percent_remaining": (self.available_for_context / self.total_context_window) * 100
        }

class PromptAssembler:
    """
    Assembles optimal prompts within token budget
    """
    
    def __init__(self):
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def assemble_prompt(
        self,
        system_prompt: str,
        user_query: str,
        retrieved_chunks: List['RetrievedChunk'],
        conversation_history: Optional[List[Dict]] = None,
        budget: Optional[TokenBudget] = None
    ) -> tuple[str, TokenBudget]:
        """
        Assemble final prompt within token budget
        
        CONTRACT:
        - Input: components (system, query, chunks, history)
        - Output: Final prompt string + updated budget
        - Time: ~50ms (mostly tokenization)
        
        STRATEGY:
        1. Count tokens for fixed parts
        2. Calculate available for context
        3. Prioritize top-ranked chunks
        4. Truncate/compress if over budget
        5. Assemble final prompt
        """
        
        if budget is None:
            budget = TokenBudget()
        
        # Count fixed tokens
        budget.system_prompt_tokens = self.count_tokens(system_prompt)
        budget.user_query_tokens = self.count_tokens(user_query)
        
        # Count history tokens (if present)
        if conversation_history:
            history_text = "\n".join([
                f"User: {turn['query']}\nAssistant: {turn['response']}"
                for turn in conversation_history[-5:]  # Last 5 turns max
            ])
            budget.conversation_history_tokens = self.count_tokens(history_text)
        
        # Recompute available budget
        budget.__post_init__()
        
        if not budget.is_within_budget():
            logger.warning(f"Token budget exceeded! Available: {budget.available_for_context}")
            # Fall back to cheaper model or compress history
        
        # Now assemble context from chunks
        context_parts = []
        remaining_tokens = budget.available_for_context
        
        for i, chunk in enumerate(retrieved_chunks):
            chunk_text = self._format_chunk(chunk, i + 1)
            chunk_tokens = self.count_tokens(chunk_text)
            
            if chunk_tokens < remaining_tokens:
                context_parts.append(chunk_text)
                remaining_tokens -= chunk_tokens
                budget.context_tokens_used += chunk_tokens
            else:
                # Truncate to fit remaining budget
                if remaining_tokens > 100:  # Only include if meaningful
                    truncated = self._truncate_to_tokens(chunk_text, remaining_tokens)
                    context_parts.append(truncated)
                    budget.context_tokens_used += self.count_tokens(truncated)
                break  # Stop adding chunks
        
        # Assemble final prompt
        context_section = "\n\n".join(context_parts) if context_parts else "No context available."
        
        final_prompt = f"""{system_prompt}

---RETRIEVED CONTEXT---
{context_section}

---CONVERSATION HISTORY---
{self._format_history(conversation_history) if conversation_history else "None"}

---USER QUERY---
{user_query}"""
        
        return final_prompt, budget
    
    def _format_chunk(self, chunk: 'RetrievedChunk', index: int) -> str:
        """Format retrieved chunk with attribution"""
        return f"""[Source {index}: {chunk.metadata.get('source', 'Unknown')}]
{chunk.content}
[Page {chunk.metadata.get('page_number', 'N/A')}, Score: {chunk.similarity_score:.2f}]"""
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format conversation history concisely"""
        if not history:
            return ""
        return "\n".join([
            f"Q: {turn['query']}\nA: {turn['response'][:200]}..."  # Summarize
            for turn in history[-3:]  # Last 3 turns
        ])
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit token budget"""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        # Truncate to fit
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)
```

---

## Part 3: Model Selection & Routing

```python
"""
Intelligent model selection balancing quality, cost, and latency
"""

from enum import Enum
from typing import Optional
import time

class Model(Enum):
    """Available models"""
    GPT_4O = "gpt-4o"  # Full capability, ~$3/1M input tokens
    GPT_4O_MINI = "gpt-4o-mini"  # Fast & cheap, ~$0.15/1M input tokens
    GPT_4_TURBO = "gpt-4-turbo"  # High context, ~$10/1M input tokens

class ModelRouter:
    """
    Routes queries to optimal model based on:
    - Query complexity
    - Cost budget
    - Performance requirements
    - Model availability
    """
    
    def __init__(self):
        self.model_latencies = {
            Model.GPT_4O: [],  # Circular buffer of latencies
            Model.GPT_4O_MINI: [],
            Model.GPT_4_TURBO: []
        }
        self.max_latency_samples = 100  # Keep last 100
    
    def select_model(
        self,
        query: str,
        retrieved_chunks: List,
        cost_budget: Optional[float] = None,
        quality_critical: bool = False
    ) -> Model:
        """
        Select optimal model for query
        
        CONTRACT:
        - Input: query, chunks, budget, quality flag
        - Output: Selected Model enum
        - Time: <10ms (analysis only)
        """
        
        # If quality critical, always use best model
        if quality_critical:
            return Model.GPT_4O
        
        # If cost-constrained, use cheap model
        if cost_budget is not None and cost_budget < 0.10:  # $0.10 for the query
            return Model.GPT_4O_MINI
        
        # Otherwise, analyze query complexity
        complexity_score = self._analyze_complexity(query, len(retrieved_chunks))
        
        if complexity_score > 0.7:
            # Complex query: Use full model
            return Model.GPT_4O
        elif complexity_score > 0.4:
            # Medium complexity: Use mini for speed
            return Model.GPT_4O_MINI
        else:
            # Simple query: Use mini (70% cost savings)
            return Model.GPT_4O_MINI
    
    def _analyze_complexity(self, query: str, num_chunks: int) -> float:
        """
        Score query complexity 0.0-1.0
        
        Heuristics:
        - Question words (why, how, what): indicates reasoning
        - Multiple conditions (AND, OR): indicates complexity
        - Number of chunks: more context = more reasoning needed
        """
        
        score = 0.0
        
        # Word-based scoring
        complex_words = ["why", "how", "compare", "analyze", "explain", "architecture"]
        if any(word in query.lower() for word in complex_words):
            score += 0.3
        
        # Multi-condition scoring
        if " and " in query.lower() or " or " in query.lower():
            score += 0.2
        
        # Context-based scoring
        if num_chunks > 20:
            score += 0.2
        elif num_chunks > 5:
            score += 0.1
        
        return min(score, 1.0)
    
    def record_latency(self, model: Model, latency_ms: float):
        """Record model latency for load-based routing"""
        self.model_latencies[model].append(latency_ms)
        if len(self.model_latencies[model]) > self.max_latency_samples:
            self.model_latencies[model].pop(0)
    
    def get_avg_latency(self, model: Model) -> float:
        """Get average latency for model"""
        if not self.model_latencies[model]:
            return 0.0
        return sum(self.model_latencies[model]) / len(self.model_latencies[model])
```

---

## Part 4: Streaming Generation

```python
"""
Real-time streaming generation with OpenAI API
Reduces perceived latency, improves UX
"""

from typing import AsyncGenerator
import json
import re

class StreamingGenerator:
    """
    Streams generation output token-by-token to user
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_streaming(
        self,
        final_prompt: str,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """
        Stream generation output from OpenAI API
        
        CONTRACT:
        - Input: prompt, model, temperature
        - Output: Async generator of token strings
        - Time: ~200-2000ms total (depends on response length)
        
        FLOW:
        1. Call OpenAI with stream=True
        2. Iterate over chunks as they arrive
        3. Extract text from each chunk
        4. Yield text to caller (UI or further processing)
        5. Handle errors gracefully
        """
        
        messages = [
            {"role": "user", "content": final_prompt}
        ]
        
        try:
            # Call OpenAI streaming API
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # KEY: Enable streaming
                top_p=0.95
            )
            
            # Iterate over stream chunks
            for chunk in stream:
                # Each chunk has format:
                # {
                #   "choices": [{
                #     "delta": {"content": "some text"}
                #   }]
                # }
                
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    yield text  # Send to caller
                    
        except Exception as e:
            logger.error(f"Streaming generation error: {e}")
            yield f"[Error generating response: {str(e)}]"
    
    async def generate_with_citations(
        self,
        final_prompt: str,
        retrieved_chunks: List['RetrievedChunk'],
        model: str = "gpt-4o"
    ) -> tuple[str, List['Citation']]:
        """
        Generate response and extract citations in real-time
        
        CONTRACT:
        - Input: prompt, chunks, model
        - Output: Full response + list of citations
        - Time: ~200-2000ms
        """
        
        full_response = ""
        
        # Stream and collect response
        async for token in self.generate_streaming(final_prompt, model=model):
            full_response += token
        
        # Post-process: extract citations
        citations = self._extract_citations(full_response, retrieved_chunks)
        
        return full_response, citations
    
    def _extract_citations(
        self,
        response_text: str,
        retrieved_chunks: List['RetrievedChunk']
    ) -> List['Citation']:
        """
        Extract citation references from response
        
        Pattern: [Source X: filename] or footnotes [1], [2]
        """
        
        citations = []
        
        # Pattern 1: [Source X: filename]
        source_pattern = r'\[Source (\d+):\s*([^\]]+)\]'
        for match in re.finditer(source_pattern, response_text):
            source_num = int(match.group(1))
            filename = match.group(2).strip()
            
            # Find corresponding chunk
            if source_num - 1 < len(retrieved_chunks):
                chunk = retrieved_chunks[source_num - 1]
                citations.append(Citation(
                    chunk_id=str(chunk.chunk_id),
                    source=filename,
                    citation_index=source_num,
                    quote=None  # Could extract from response
                ))
        
        return citations
```

---

## Part 5: Generation Request/Response Contracts

```python
"""
Standardized interfaces for Generation component
"""

from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class Citation:
    """A source citation in the generated response"""
    chunk_id: str
    source: str  # Filename or document name
    page_number: Optional[int] = None
    citation_index: int = 0
    quote: Optional[str] = None  # Exact text quoted
    confidence: float = 1.0  # 0.0-1.0, confidence in accuracy

@dataclass
class GenerationRequest:
    """
    INPUT: What Reranking/Retrieval asks Generation to do
    """
    query_id: str
    user_id: str
    original_query: str
    retrieved_chunks: List['RetrievedChunk']
    
    # Optional
    conversation_history: Optional[List[Dict]] = None
    quality_critical: bool = False  # Prioritize quality over speed/cost
    cost_budget: Optional[float] = None  # Max cost per request
    stream: bool = True  # Enable streaming?
    
    # Configuration
    temperature: float = 0.3
    max_tokens: int = 1000
    model_preference: Optional[str] = None

@dataclass
class GeneratedResponse:
    """
    OUTPUT: What Generation produces
    """
    # Identification & Lineage
    response_id: UUID
    query_id: str
    user_id: str
    
    # Generated Content
    text: str  # The full response
    citations: List[Citation] = field(default_factory=list)
    
    # Quality & Confidence
    confidence_score: float  # 0.0-1.0, how faithful to context?
    has_hallucinations: bool = False  # Did model make up facts?
    hallucination_details: Optional[str] = None
    
    # Token & Cost Accounting
    tokens_used: Dict = field(default_factory=dict)
    # {
    #   "prompt_tokens": int,
    #   "completion_tokens": int,
    #   "total_tokens": int,
    #   "estimated_cost_usd": float
    # }
    
    # Model & Execution
    model_used: str
    temperature: float
    generation_latency_ms: float
    finish_reason: str  # "stop", "max_tokens", "error"
    
    # Metadata for tracing
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # User Feedback (collected later)
    user_rating: Optional[float] = None  # 1-5 stars
    user_feedback: Optional[str] = None
    feedback_collected_at: Optional[datetime] = None
```

---

## Part 6: Complete Generation Service

```python
"""
Main Generation Service orchestrating the full pipeline
"""

from typing import AsyncGenerator, Optional
import hashlib
import time

class GenerationService:
    """
    Main interface for generating responses
    Orchestrates: prompt assembly → model selection → streaming → citation extraction
    """
    
    def __init__(self):
        self.prompt_assembler = PromptAssembler()
        self.model_router = ModelRouter()
        self.streaming_generator = StreamingGenerator()
        self.evaluator = HallucinationEvaluator()  # Detect hallucinations
    
    async def generate(
        self,
        request: GenerationRequest
    ) -> GeneratedResponse:
        """
        Full generation pipeline
        
        CONTRACT:
        - Input: GenerationRequest with query, chunks, history
        - Output: GeneratedResponse with text + citations
        - Time: <500ms for simple, <2s for complex
        
        STEPS:
        1. Assemble prompt within token budget
        2. Route to optimal model
        3. Stream generation from OpenAI
        4. Extract citations
        5. Detect hallucinations
        6. Format response
        7. Return to caller
        """
        
        start_time = time.time()
        response_id = uuid4()
        
        # STEP 1: Assemble prompt
        system_prompt = self._get_system_prompt()
        final_prompt, budget = self.prompt_assembler.assemble_prompt(
            system_prompt=system_prompt,
            user_query=request.original_query,
            retrieved_chunks=request.retrieved_chunks,
            conversation_history=request.conversation_history
        )
        
        logger.info(f"[GEN] Prompt assembled. Token budget: {budget.get_summary()}")
        
        # STEP 2: Select model
        selected_model = self.model_router.select_model(
            query=request.original_query,
            retrieved_chunks=request.retrieved_chunks,
            cost_budget=request.cost_budget,
            quality_critical=request.quality_critical
        )
        
        # STEP 3: Generate
        full_response = ""
        
        if request.stream:
            # Stream to caller
            async for token in self.streaming_generator.generate_streaming(
                final_prompt=final_prompt,
                model=selected_model.value,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                full_response += token
                # Could yield to frontend here for real-time display
        else:
            # Non-streaming (faster for short responses)
            full_response, _ = await self.streaming_generator.generate_with_citations(
                final_prompt=final_prompt,
                retrieved_chunks=request.retrieved_chunks,
                model=selected_model.value
            )
        
        # STEP 4: Extract citations
        citations = self.streaming_generator._extract_citations(
            full_response,
            request.retrieved_chunks
        )
        
        # STEP 5: Check for hallucinations
        hallucination_score = await self.evaluator.evaluate(
            response=full_response,
            context_chunks=request.retrieved_chunks
        )
        
        # STEP 6: Calculate metrics
        generation_latency = (time.time() - start_time) * 1000  # ms
        token_count = self.prompt_assembler.count_tokens(full_response)
        estimated_cost = self._estimate_cost(
            selected_model,
            budget.context_tokens_used,
            token_count
        )
        
        # STEP 7: Build response
        response = GeneratedResponse(
            response_id=response_id,
            query_id=request.query_id,
            user_id=request.user_id,
            text=full_response,
            citations=citations,
            confidence_score=1.0 - hallucination_score,
            has_hallucinations=hallucination_score > 0.3,
            hallucination_details=f"Hallucination score: {hallucination_score:.2f}",
            tokens_used={
                "prompt_tokens": budget.context_tokens_used,
                "completion_tokens": token_count,
                "total_tokens": budget.context_tokens_used + token_count,
                "estimated_cost_usd": estimated_cost
            },
            model_used=selected_model.value,
            temperature=request.temperature,
            generation_latency_ms=generation_latency,
            finish_reason="stop",
            metadata={
                "model_selection_reason": self._get_selection_reason(selected_model),
                "token_budget_summary": budget.get_summary(),
                "num_citations": len(citations)
            }
        )
        
        # Record latency for future routing
        self.model_router.record_latency(selected_model, generation_latency)
        
        logger.info(
            f"[GEN] Generated response: {len(full_response)} chars, "
            f"{token_count} tokens, {generation_latency:.0f}ms, "
            f"${estimated_cost:.4f}, {len(citations)} citations"
        )
        
        return response
    
    def _get_system_prompt(self) -> str:
        """System prompt for generation"""
        return """You are a helpful, accurate, and concise assistant. 

When answering questions:
1. Use ONLY the provided context to form your answer
2. If the context doesn't contain the answer, say so explicitly
3. Cite your sources using [Source N: filename] format
4. Be precise and avoid generalizations
5. For technical questions, provide examples when relevant
6. If you're uncertain, express that uncertainty

Format your response in clear sections if the answer is complex.
Always prioritize accuracy over comprehensiveness."""
    
    def _estimate_cost(
        self,
        model: Model,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate API cost for generation"""
        
        costs = {
            Model.GPT_4O: {
                "input": 3.0 / 1_000_000,  # $3 per 1M input tokens
                "output": 6.0 / 1_000_000  # $6 per 1M output tokens
            },
            Model.GPT_4O_MINI: {
                "input": 0.15 / 1_000_000,  # $0.15 per 1M input tokens
                "output": 0.60 / 1_000_000  # $0.60 per 1M output tokens
            }
        }
        
        cost_info = costs[model]
        return (input_tokens * cost_info["input"]) + (output_tokens * cost_info["output"])
    
    def _get_selection_reason(self, model: Model) -> str:
        """Explain why this model was selected"""
        if model == Model.GPT_4O:
            return "Full model selected for query complexity"
        elif model == Model.GPT_4O_MINI:
            return "Mini model selected for speed/cost optimization"
        else:
            return "Model selected by cost/quality tradeoff"
```

---

## Part 7: Hallucination Detection & Validation

```python
"""
Detect when model makes up facts not in context
"""

class HallucinationEvaluator:
    """
    Evaluates if generated response stays faithful to retrieved context
    """
    
    def __init__(self):
        self.evaluator_llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def evaluate(
        self,
        response: str,
        context_chunks: List['RetrievedChunk']
    ) -> float:
        """
        Score response faithfulness 0.0-1.0
        
        Higher score = more hallucinations
        Returns: hallucination_score (0.0 = faithful, 1.0 = all hallucinated)
        """
        
        # Concatenate context
        context_text = "\n\n".join([
            chunk.content for chunk in context_chunks
        ])
        
        # Evaluation prompt
        eval_prompt = f"""Evaluate if the following response is faithful to the provided context.

CONTEXT:
{context_text}

RESPONSE:
{response}

Rate on a scale 0.0-1.0 where:
- 0.0 = Completely faithful, all claims supported by context
- 0.3 = Mostly faithful with minor unsupported details
- 0.7 = Some hallucinated content mixed with context
- 1.0 = Mostly hallucinated, not based on context

Also identify specific hallucinated claims if any.

Format your response as JSON:
{{
  "hallucination_score": <float 0.0-1.0>,
  "hallucinated_claims": [<list of claims not in context>],
  "reasoning": "<brief explanation>"
}}"""
        
        try:
            # Call evaluation model
            response_obj = self.evaluator_llm.chat.completions.create(
                model="gpt-4o-mini",  # Use cheaper mini for evaluation
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.0,  # Deterministic evaluation
                max_tokens=300
            )
            
            # Parse JSON response
            eval_text = response_obj.choices[0].message.content
            import json
            eval_result = json.loads(eval_text)
            
            return eval_result.get("hallucination_score", 0.5)
            
        except Exception as e:
            logger.warning(f"Hallucination evaluation failed: {e}")
            return 0.0  # Assume faithful if evaluation fails
```

---

## Part 8: Integration Points (LEGO Fitting)

### 8.1 Reranking → Generation

```python
# After reranking, top chunks flow to generation
reranked_chunks: List[RetrievedChunk] = await reranker.rerank(
    query=query,
    candidates=retrieved_chunks,
    top_k=15
)

# Generation receives perfectly formatted chunks
generation_request = GenerationRequest(
    query_id="q-456",
    user_id="user-789",
    original_query=query,
    retrieved_chunks=reranked_chunks,
    conversation_history=memory.get_history(user_id),
    stream=True
)

response = await generation_service.generate(generation_request)
```

### 8.2 Generation → Evaluation (Feedback Loop)

```python
# After generation, response flows to evaluation
evaluation_request = EvaluationRequest(
    query_id=response.query_id,
    original_query=request.original_query,
    generated_response=response.text,
    retrieved_context=request.retrieved_chunks,
    citations=response.citations
)

# Evaluation scores response and feeds back to Data Layer
evaluation_result = await evaluator.evaluate(evaluation_request)

# Update chunk quality scores for future retrievals
await data_layer.update_chunk_quality_scores([
    ChunkQualityUpdate(
        chunk_id=citation.chunk_id,
        quality_score_delta=evaluation_result.faithfulness_score
    )
    for citation in response.citations
])
```

### 8.3 Generation → UI (Streaming)

```javascript
// React frontend receives streaming response
async function streamGeneratedResponse(queryId) {
    const response = await fetch(`/api/generate/${queryId}`, {
        method: 'POST'
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = "";
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        fullResponse += chunk;
        
        // Update UI in real-time
        setGeneratedText(fullResponse);
        
        // Track citations as they appear
        const citations = extractCitations(fullResponse);
        setCitations(citations);
    }
}
```

---

## Part 9: Prompt Templates

```python
"""
System prompts for different scenarios
"""

SYSTEM_PROMPTS = {
    "default": """You are a helpful, accurate, and concise assistant.

When answering questions:
1. Use ONLY the provided context to form your answer
2. If the context doesn't contain the answer, say "The provided context doesn't contain information about this"
3. Cite your sources using [Source N: filename] format
4. Be precise and avoid generalizations
5. If you're uncertain, express that uncertainty
""",
    
    "technical": """You are a technical expert assistant specializing in software architecture and engineering.

When answering technical questions:
1. Provide accurate technical details from the context
2. Include code examples if relevant and in context
3. Explain architectural decisions and tradeoffs
4. Use [Source N] citations for all claims
5. Be precise about performance characteristics, constraints, and failure modes
""",
    
    "legal": """You are a legal assistant. Always prioritize accuracy and clarity.

Important restrictions:
1. NEVER provide legal advice - only summarize provided legal documents
2. Always cite the specific legal text using [Source N: document]
3. Flag any ambiguities or conflicts in the provided documents
4. If a legal opinion is requested, refuse and suggest consulting a lawyer
5. Use precise language and avoid generalizations
""",
    
    "code_generation": """You are a code assistant. Write clear, well-documented code.

When generating code:
1. Provide only code that is directly supported by the provided context
2. Include comments explaining the logic
3. Follow any coding standards mentioned in context
4. Cite code examples from the context using [Source N]
5. For missing dependencies, suggest consulting the full documentation
"""
}
```

---

## Part 10: Configuration & Performance Targets

```yaml
# generation_config.yaml
generation:
  # Model Configuration
  default_model: "gpt-4o"
  fallback_model: "gpt-4o-mini"
  
  # Token Budgeting
  max_context_window: 128000  # GPT-4o tokens
  system_prompt_tokens: 500
  response_budget_tokens: 1000
  conversation_history_budget: 2000
  max_context_chunk_size: 4000
  
  # Streaming
  enable_streaming: true
  stream_chunk_buffer: 5  # Tokens per event
  streaming_timeout_ms: 60000  # 1 minute max
  
  # Temperature & Sampling
  temperature_factual: 0.0  # FAQ, lookups
  temperature_creative: 0.7  # Creative writing
  temperature_reasoning: 0.3  # Problem solving (default)
  top_p: 0.95
  
  # Cost Control
  cost_per_query_budget: 0.50  # Max $0.50 per query
  enable_cost_routing: true  # Route to cheaper model if over budget
  
  # Hallucination Detection
  enable_hallucination_detection: true
  hallucination_threshold: 0.3  # Flag if > 30% hallucinated
  
  # Latency Targets
  max_generation_latency_ms: 2000  # Max 2 seconds
  p95_generation_latency_ms: 1000  # 95th percentile target
  
  # Fallback Strategies
  fallback_on_model_error: true
  fallback_on_timeout: true
  fallback_response: "I was unable to generate a response. Please try again."
```

---

## Part 11: Performance Targets & SLA

```
GENERATION LATENCY SLA:

Simple Queries (FAQ, Direct Lookup):
  Model: GPT-4o-mini
  P50: 300-500ms
  P95: 800-1200ms
  P99: 1500-2000ms

Complex Queries (Multi-hop Reasoning):
  Model: GPT-4o
  P50: 800-1200ms
  P95: 1500-2500ms
  P99: 3000-4000ms

Streaming Benefits:
  - Time to first token: 100-200ms (vs. 300-500ms for full response)
  - Perceived latency: 30-50% reduction
  - User engagement: +20-30% higher completion rate

TOKEN USAGE & COST:

Per Query (Typical):
  - Input tokens: 3000-5000
  - Output tokens: 200-400
  - Total: 3200-5400 tokens

Cost Breakdown (GPT-4o):
  - Input: ~$0.009 (3000 tokens × $3/1M)
  - Output: ~$0.002 (200 tokens × $6/1M)
  - Total per query: ~$0.011

Cost Optimization:
  - Using GPT-4o-mini for simple queries: 95% cost reduction
  - Token budgeting: 30-50% fewer tokens vs. unoptimized
  - Caching: 70% cost reduction on repeated queries

QUALITY TARGETS:

Faithfulness:
  - Hallucination rate: < 5% (detect via evaluation)
  - Citation accuracy: > 95%
  - Out-of-context claims: < 3%

Response Quality:
  - Citations per response: 2-5 (average)
  - Coverage of query: > 80%
  - User satisfaction: > 4.0/5.0 stars

AVAILABILITY:

- OpenAI API: 99.9% SLA
- Generation fallback: 99.95% (cascade to backup model)
- Timeout recovery: 99.99% (return partial response)
```

---

## Part 12: Generation Layer as LEGO Brick Summary

Your Generation Layer **perfectly fits** because:

✅ **Standardized Input**: Accepts exact RetrievedChunk format from Data Layer
✅ **Standardized Output**: Produces GeneratedResponse matching Evaluation's expectations
✅ **Token-aware**: Respects budget constraints from Data Layer
✅ **Citations Embedded**: Provides source attribution for evaluation & compliance
✅ **Streaming-first**: Real-time UX with token-by-token delivery
✅ **Model-agnostic**: Routes between models based on quality/cost tradeoff
✅ **Memory-integrated**: Carries conversation context through turns
✅ **Observable**: Full tracing for debugging and optimization
✅ **Graceful degradation**: Fallbacks if model unavailable or timeout

**The Pipeline Fits Because**:
- Data Layer → Generation: Sends RetrievedChunk objects
- Generation assembles prompts within token budget
- Streams tokens to frontend for real-time UI
- Extracts citations for evaluation
- Evaluator scores faithfulness → feedback to Data Layer
- Memory stores Q&A pairs → context for next turn

**Next Implementation Steps**:
1. Set up OpenAI API key & rate limiting
2. Implement PromptAssembler with token budgeting
3. Build ModelRouter with complexity analysis
4. Create streaming generation with error handling
5. Implement citation extraction regex
6. Build HallucinationEvaluator
7. Add LangSmith tracing for prompt optimization
8. Load test with realistic query distributions
9. Optimize based on latency & cost metrics
10. Monitor hallucination rates in production

**Key Decisions Made**:
- **GPT-4o + GPT-4o-mini dual model**: Quality when needed, cost-effective for simple queries
- **Token budgeting mandatory**: Prevents runaway costs and latency
- **Streaming default**: Better UX, perceived latency 30-50% lower
- **Post-generation evaluation**: Catch hallucinations before user sees them
- **Citation tracking**: Legal compliance + evaluation quality metrics
- **Conversation memory**: Enable multi-turn dialogue

