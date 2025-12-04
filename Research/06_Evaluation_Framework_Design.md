# Evaluation Framework Design - Production RAG System

## Executive Summary

The **Evaluation Framework** is the quality control system of your RAG pipeline. It receives generated responses and measures their quality across 4 critical dimensions: **Faithfulness** (hallucination detection), **Answer Relevancy** (usefulness to user), **Context Recall** (retriever completeness), and **Context Precision** (retriever accuracy). It operates as a **multi-metric, feedback-driven evaluation pipeline** with:

- **RAGAS Metrics**: Industry-standard reference-free evaluation using LLM-based assessments
- **Component-Level Diagnostics**: Separate evaluation of retriever vs. generator performance
- **Continuous Feedback Loops**: Quality scores flow back to Data Layer for chunk re-ranking
- **Production Monitoring**: Real-time dashboards with LangSmith tracing integration
- **User Feedback Collection**: Explicit ratings (1-5 stars) + implicit signals (usage patterns)
- **Synthetic Dataset Generation**: Create test data automatically from production documents
- **Performance Regression Detection**: Alert if quality drops below thresholds

This design treats the Evaluation Framework as a **LEGO brick** that:
✓ Accepts precisely-formatted GeneratedResponse objects from Generation Layer
✓ Measures quality across multiple dimensions (no single-metric bias)
✓ Generates actionable diagnostics (retriever vs. generator attribution)
✓ Creates feedback signals flowing back to Data/Generation layers
✓ Provides production observability via LangSmith + dashboards
✓ Enables continuous improvement through A/B testing and experimentation
✓ Maintains dataset quality through synthetic generation and ground truth collection

---

## Part 1: Architecture Overview

### Evaluation Pipeline - The LEGO Brick

```
┌─────────────────────────────────────────────────────────────────┐
│         EVALUATION FRAMEWORK (Multi-Metric Quality Loop)         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  INPUT: GeneratedResponse from Generation Layer                 │
│  ├─ generated_text: str (LLM response)                          │
│  ├─ citations: List[Citation] (sources used)                   │
│  ├─ retrieved_chunks: List[RetrievedChunk] (context provided)  │
│  ├─ original_query: str (user question)                        │
│  ├─ model_used: str                                             │
│  └─ metadata: Dict (for tracing)                               │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  STAGE 1: RETRIEVER EVALUATION                             │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Context Recall                                         │ │
│  │  │  ├─ Question: "Did retriever find ALL necessary info?"  │ │
│  │  │  ├─ Requires ground truth: ideal_chunks                │ │
│  │  │  ├─ Metric: % of ideal chunks retrieved                │ │
│  │  │  ├─ Formula: recall = retrieved_ideal / total_ideal     │ │
│  │  │  └─ Target: > 0.85 (should get 85% of needed info)     │ │
│  │  │                                                           │ │
│  │  ├─ Context Precision                                      │ │
│  │  │  ├─ Question: "How many retrieved chunks were useful?"  │ │
│  │  │  ├─ LLM scores each chunk: 0=irrelevant, 1=relevant    │ │
│  │  │  ├─ Formula: precision = relevant_chunks / total_chunks│ │
│  │  │  ├─ Score: 0.0-1.0                                      │ │
│  │  │  └─ Target: > 0.8 (at least 80% of chunks matter)      │ │
│  │  │                                                           │ │
│  │  └─ Noise Sensitivity                                      │ │
│  │     ├─ Question: "How does extra junk affect generation?"  │ │
│  │     ├─ Add 3 irrelevant chunks to retrieved set            │ │
│  │     ├─ Re-generate answer, compare quality                 │ │
│  │     └─ Score drop = noise_sensitivity (0-1, lower=better)  │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  STAGE 2: GENERATION EVALUATION                            │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Faithfulness                                           │ │
│  │  │  ├─ Question: "Is response grounded in context?"        │ │
│  │  │  ├─ Extract claims from response                        │ │
│  │  │  ├─ Check each claim against retrieved chunks           │ │
│  │  │  ├─ LLM entailment scoring: supported or hallucinated?  │ │
│  │  │  ├─ Score: 0.0-1.0 (0=all hallucinated, 1=100% true)   │ │
│  │  │  └─ Target: > 0.9 (< 10% hallucination rate)           │ │
│  │  │                                                           │ │
│  │  ├─ Answer Relevancy                                       │ │
│  │  │  ├─ Question: "Does response actually answer the query?"│ │
│  │  │  ├─ LLM evaluates: is answer on-topic?                 │ │
│  │  │  ├─ Semantic similarity between answer & query          │ │
│  │  │  ├─ Checks if all aspects of query addressed           │ │
│  │  │  ├─ Score: 0.0-1.0                                      │ │
│  │  │  └─ Target: > 0.85 (answer is relevant to user)        │ │
│  │  │                                                           │ │
│  │  └─ Answer Correctness (Optional, requires ground truth)   │ │
│  │     ├─ Question: "Is the answer factually correct?"        │ │
│  │     ├─ Requires ideal_answer for comparison                │ │
│  │     ├─ Exact match or semantic similarity with ideal       │ │
│  │     ├─ Score: 0.0-1.0                                      │ │
│  │     └─ Target: > 0.90 (90% accuracy)                       │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  STAGE 3: CITATION VALIDATION                              │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Citation Accuracy                                      │ │
│  │  │  ├─ Do citations match the chunks used?                │ │
│  │  │  ├─ Are quoted texts actually in source?               │ │
│  │  │  ├─ Verify chunk_id matches content                    │ │
│  │  │  └─ Score: % of correct citations                      │ │
│  │  │                                                           │ │
│  │  └─ Citation Completeness                                  │ │
│  │     ├─ Are all used chunks cited?                          │ │
│  │     ├─ LLM checks if response uses chunks without citing   │ │
│  │     └─ Score: % of used chunks properly cited              │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  STAGE 4: SYNTHESIS & FEEDBACK GENERATION                  │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  ┌─ RAGAS Score Calculation                                │ │
│  │  │  ├─ Weighted average of all metrics                     │ │
│  │  │  ├─ Formula: ragas_score = 0.25*(faithfulness)         │ │
│  │  │  │           + 0.25*(answer_relevancy)                  │ │
│  │  │  │           + 0.25*(context_precision)                 │ │
│  │  │  │           + 0.25*(context_recall)                    │ │
│  │  │  └─ Range: 0.0-1.0                                      │ │
│  │  │                                                           │ │
│  │  ├─ Root Cause Attribution                                 │ │
│  │  │  ├─ Low faithfulness → Generator problem                │ │
│  │  │  ├─ Low relevancy → Generator problem                   │ │
│  │  │  ├─ Low precision → Retriever problem                   │ │
│  │  │  ├─ Low recall → Retriever problem                      │ │
│  │  │  └─ Diagnosis report: which component to fix?           │ │
│  │  │                                                           │ │
│  │  └─ Feedback Signals for Improvement                       │ │
│  │     ├─ Chunk quality scores → Data Layer                   │ │
│  │     ├─ Prompt suggestions → Generation Layer               │ │
│  │     ├─ Retrieval strategy notes → Retriever                │ │
│  │     ├─ Dataset improvements → Synthetic generation         │ │
│  │     └─ Model selection hints → next generation call        │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  STAGE 5: PRODUCTION MONITORING & ALERTING                 │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  ┌─ Real-Time Dashboards                                   │ │
│  │  │  ├─ RAGAS score over time (rolling 24h, 7d, 30d)       │ │
│  │  │  ├─ Metric breakdown: faithfulness, relevancy, etc.    │ │
│  │  │  ├─ Retriever vs. Generator health separately          │ │
│  │  │  ├─ Cost per query, latency, hallucination rate        │ │
│  │  │  └─ Top failing queries (< 0.5 score)                  │ │
│  │  │                                                           │ │
│  │  ├─ Alerting Thresholds                                    │ │
│  │  │  ├─ RAGAS score drop > 10% → alert                     │ │
│  │  │  ├─ Hallucination rate > 15% → alert                   │ │
│  │  │  ├─ Context precision < 0.7 → alert                    │ │
│  │  │  ├─ Answer relevancy < 0.8 → alert                     │ │
│  │  │  └─ Negative user feedback spike → alert                │ │
│  │  │                                                           │ │
│  │  └─ Integration with LangSmith                             │ │
│  │     ├─ Traces: query → retrieval → generation → eval      │ │
│  │     ├─ Scores: attach RAGAS metrics to traces              │ │
│  │     ├─ Feedback: collect user ratings in UI                │ │
│  │     └─ A/B Testing: compare variant scores                 │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  OUTPUT: EvaluationResult object                               │
│  ├─ ragas_score: float (0.0-1.0)                              │
│  ├─ metric_scores: Dict (faithfulness, recall, etc.)          │ │
│  ├─ component_attribution: str ("retriever" or "generator")   │ │
│  ├─ detailed_feedback: str (human-readable diagnosis)         │ │
│  ├─ suggested_improvements: List[str]                         │ │
│  ├─ quality_tier: str ("excellent"/"good"/"fair"/"poor")     │ │
│  └─ feedback_signals: Dict (updates to Data/Gen layers)       │ │
│                                                                   │
│  FEEDBACK LOOP: Scores → Data Layer (chunk quality)           │ │
│                 Scores → Generation (prompt tuning)            │ │
│                 Scores → Retriever (strategy adjustment)       │ │
│                 Scores → Synthetic Dataset (gaps to fill)      │ │
│                 User Feedback → Continuous improvement         │ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: RAGAS Metric Definitions & Implementation

### 2.1 Faithfulness (Hallucination Detection)

**Question**: "Is the generated answer grounded in the retrieved context?"

**Why it matters**: Users trust you when answers come from documents. Hallucinations erode trust instantly.

```python
"""
Faithfulness: Measures grounding of answer in context (0.0-1.0)
- 1.0 = All statements supported by context
- 0.7 = Mostly supported with minor unsupported details
- 0.3 = Many hallucinated claims
- 0.0 = Entirely made up, not in context
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class FaithfulnessResult:
    score: float  # 0.0-1.0
    claims: List[Dict]  # Each claim: {text, supported: bool, source: str}
    hallucinated_claims: List[str]  # Claims not in context
    faithfulness_rating: str  # "excellent", "good", "fair", "poor"

class FaithfulnessEvaluator:
    """
    LLM-based faithfulness evaluation using entailment
    """
    
    def __init__(self):
        self.eval_llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def evaluate_faithfulness(
        self,
        answer: str,
        context_chunks: List[str]
    ) -> FaithfulnessResult:
        """
        Evaluate if answer is faithful to context
        
        CONTRACT:
        - Input: answer text, retrieved context chunks
        - Output: Faithfulness score 0.0-1.0 + identified hallucinations
        - Time: ~2-5s (LLM evaluation)
        
        ALGORITHM:
        1. Extract claims from answer (NLI - Natural Language Inference)
        2. For each claim, check against context chunks
        3. Use entailment model to verify: "Is claim supported by context?"
        4. Score = (supported_claims / total_claims)
        """
        
        context_text = "\n".join(context_chunks)
        
        # Step 1: Extract claims from answer
        extract_prompt = f"""Extract factual claims from the following answer. 
        Return as JSON list of strings.
        
        ANSWER: {answer}
        
        Return format: {{"claims": ["claim 1", "claim 2", ...]}}"""
        
        extract_response = await self.eval_llm.chat.completions.create(
            model="gpt-4o-mini",  # Use mini for speed
            messages=[{"role": "user", "content": extract_prompt}],
            temperature=0.0,
            max_tokens=500
        )
        
        try:
            claims_data = json.loads(extract_response.choices[0].message.content)
            claims_list = claims_data.get("claims", [])
        except:
            claims_list = answer.split(". ")  # Fallback
        
        # Step 2: Verify each claim against context
        claim_verifications = []
        supported_count = 0
        
        for claim in claims_list:
            # Use entailment to check if context supports claim
            entailment_prompt = f"""Does the following CONTEXT support the CLAIM?

CONTEXT:
{context_text}

CLAIM: {claim}

Answer with JSON: {{"supported": true/false, "explanation": "..."}}"""
            
            entail_response = await self.eval_llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": entailment_prompt}],
                temperature=0.0,
                max_tokens=200
            )
            
            try:
                entail_data = json.loads(entail_response.choices[0].message.content)
                supported = entail_data.get("supported", False)
            except:
                supported = False
            
            if supported:
                supported_count += 1
            
            claim_verifications.append({
                "text": claim,
                "supported": supported,
                "explanation": entail_data.get("explanation", "")
            })
        
        # Step 3: Calculate score
        if len(claims_list) == 0:
            faithfulness_score = 1.0  # No claims = trivially faithful
        else:
            faithfulness_score = supported_count / len(claims_list)
        
        # Step 4: Categorize
        if faithfulness_score > 0.9:
            rating = "excellent"
        elif faithfulness_score > 0.75:
            rating = "good"
        elif faithfulness_score > 0.5:
            rating = "fair"
        else:
            rating = "poor"
        
        hallucinated = [c["text"] for c in claim_verifications if not c["supported"]]
        
        logger.info(f"[EVAL] Faithfulness: {faithfulness_score:.2f} "
                   f"({supported_count}/{len(claims_list)} claims supported)")
        
        return FaithfulnessResult(
            score=faithfulness_score,
            claims=claim_verifications,
            hallucinated_claims=hallucinated,
            faithfulness_rating=rating
        )
```

### 2.2 Answer Relevancy (Usefulness to User)

**Question**: "Does the answer actually address what the user asked?"

**Why it matters**: A faithful but irrelevant answer is useless. "The sky is blue" is true but doesn't help if you asked about diabetes treatment.

```python
@dataclass
class AnswerRelevancyResult:
    score: float  # 0.0-1.0
    addresses_all_aspects: bool
    reasoning: str
    relevancy_rating: str

class AnswerRelevancyEvaluator:
    """
    Evaluates how well answer addresses the user's query
    """
    
    def __init__(self):
        self.eval_llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def evaluate_relevancy(
        self,
        query: str,
        answer: str,
        context: str
    ) -> AnswerRelevancyResult:
        """
        Evaluate if answer is relevant to query
        
        CONTRACT:
        - Input: user query, generated answer, context
        - Output: Relevancy score 0.0-1.0
        - Time: ~1-2s
        
        EVALUATION ASPECTS:
        1. Is answer on-topic?
        2. Does answer address all aspects of the query?
        3. Is answer within scope of provided context?
        4. Semantic similarity between answer and query intent?
        """
        
        eval_prompt = f"""Evaluate how well this ANSWER addresses the USER QUERY.

USER QUERY: {query}

ANSWER: {answer}

CONTEXT PROVIDED: {context}

Evaluate on these criteria:
1. On-topic: Does answer relate to the query?
2. Complete: Does it address all parts of the query?
3. Scope: Is answer within the provided context?
4. Usefulness: Would this answer help someone asking the query?

Rate on 0.0-1.0 scale and explain your reasoning.

Format as JSON:
{{
  "relevancy_score": <float 0.0-1.0>,
  "on_topic": true/false,
  "addresses_all_aspects": true/false,
  "within_scope": true/false,
  "reasoning": "<explanation>"
}}"""
        
        response = await self.eval_llm.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": eval_prompt}],
            temperature=0.0,
            max_tokens=300
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            score = result.get("relevancy_score", 0.5)
            addresses_all = result.get("addresses_all_aspects", False)
            reasoning = result.get("reasoning", "")
        except:
            score = 0.5
            addresses_all = False
            reasoning = "Evaluation failed"
        
        # Categorize
        if score > 0.9:
            rating = "excellent"
        elif score > 0.75:
            rating = "good"
        elif score > 0.5:
            rating = "fair"
        else:
            rating = "poor"
        
        logger.info(f"[EVAL] Answer Relevancy: {score:.2f}, "
                   f"Addresses all: {addresses_all}")
        
        return AnswerRelevancyResult(
            score=score,
            addresses_all_aspects=addresses_all,
            reasoning=reasoning,
            relevancy_rating=rating
        )
```

### 2.3 Context Recall (Retriever Completeness)

**Question**: "Did the retriever find all the information needed to answer?"

**Why it matters**: If the retriever misses crucial documents, even a perfect generator can't help. Requires **ground truth**.

```python
@dataclass
class ContextRecallResult:
    score: float  # 0.0-1.0
    num_ideal_chunks_retrieved: int
    num_ideal_chunks_total: int
    missing_chunks: List[str]  # Content of chunks that should have been retrieved
    recall_rating: str

class ContextRecallEvaluator:
    """
    Evaluates if retriever found all necessary context
    Requires ground truth: which chunks are ideal for this query?
    """
    
    async def evaluate_context_recall(
        self,
        retrieved_chunks: List[str],
        ideal_chunks: List[str],  # Ground truth: chunks needed to answer
    ) -> ContextRecallResult:
        """
        Evaluate retriever recall
        
        CONTRACT:
        - Input: what retriever returned, what it should have found
        - Output: Recall score 0.0-1.0
        - Time: <100ms (no LLM needed - direct comparison)
        
        FORMULA:
        recall = (# ideal chunks that were retrieved) / (# ideal chunks total)
        """
        
        # For each ideal chunk, check if it (or semantically similar) was retrieved
        retrieved_set = set(retrieved_chunks)
        matched_count = 0
        
        for ideal_chunk in ideal_chunks:
            # Check for exact match
            if ideal_chunk in retrieved_set:
                matched_count += 1
            else:
                # Check for semantic similarity (use embedding)
                # This is simplified - in practice use embedding similarity
                pass
        
        recall_score = matched_count / len(ideal_chunks) if ideal_chunks else 1.0
        
        missing = [c for c in ideal_chunks if c not in retrieved_set]
        
        if recall_score > 0.9:
            rating = "excellent"
        elif recall_score > 0.7:
            rating = "good"
        elif recall_score > 0.5:
            rating = "fair"
        else:
            rating = "poor"
        
        logger.info(f"[EVAL] Context Recall: {recall_score:.2f} "
                   f"({matched_count}/{len(ideal_chunks)})")
        
        return ContextRecallResult(
            score=recall_score,
            num_ideal_chunks_retrieved=matched_count,
            num_ideal_chunks_total=len(ideal_chunks),
            missing_chunks=missing,
            recall_rating=rating
        )
```

### 2.4 Context Precision (Retriever Accuracy)

**Question**: "Of the chunks the retriever returned, how many were actually useful?"

**Why it matters**: Too much irrelevant context wastes tokens, adds noise, confuses the generator.

```python
@dataclass
class ContextPrecisionResult:
    score: float  # 0.0-1.0
    relevant_chunks: int
    total_chunks: int
    precision_rating: str
    irrelevant_analysis: List[Dict]  # {"chunk": str, "why_irrelevant": str}

class ContextPrecisionEvaluator:
    """
    Evaluates precision of retrieved context
    Uses LLM to judge: is each chunk relevant to the query?
    """
    
    def __init__(self):
        self.eval_llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def evaluate_context_precision(
        self,
        query: str,
        retrieved_chunks: List[str],
        top_k: int = 10  # Only evaluate top-k (cheaper)
    ) -> ContextPrecisionResult:
        """
        Evaluate precision of retrieved chunks
        
        CONTRACT:
        - Input: query, retrieved chunks
        - Output: Precision score 0.0-1.0
        - Time: ~2-5s per chunk (LLM evaluation)
        """
        
        relevant_count = 0
        irrelevant_analysis = []
        
        # Only evaluate top-k to save cost
        chunks_to_eval = retrieved_chunks[:top_k]
        
        for i, chunk in enumerate(chunks_to_eval):
            eval_prompt = f"""Is this CHUNK relevant and useful for answering the QUERY?

QUERY: {query}

CHUNK:
{chunk}

Answer with JSON:
{{
  "relevant": true/false,
  "relevance_score": <0.0-1.0>,
  "reasoning": "<explanation>"
}}"""
            
            response = await self.eval_llm.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for speed
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.0,
                max_tokens=150
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                is_relevant = result.get("relevant", False)
                relevance_score = result.get("relevance_score", 0.5)
                reasoning = result.get("reasoning", "")
            except:
                is_relevant = False
                relevance_score = 0.0
                reasoning = "Evaluation failed"
            
            if is_relevant:
                relevant_count += 1
            else:
                irrelevant_analysis.append({
                    "chunk_index": i,
                    "chunk_preview": chunk[:100],
                    "relevance_score": relevance_score,
                    "reasoning": reasoning
                })
        
        precision = relevant_count / len(chunks_to_eval) if chunks_to_eval else 1.0
        
        if precision > 0.9:
            rating = "excellent"
        elif precision > 0.75:
            rating = "good"
        elif precision > 0.6:
            rating = "fair"
        else:
            rating = "poor"
        
        logger.info(f"[EVAL] Context Precision: {precision:.2f} "
                   f"({relevant_count}/{len(chunks_to_eval)})")
        
        return ContextPrecisionResult(
            score=precision,
            relevant_chunks=relevant_count,
            total_chunks=len(chunks_to_eval),
            precision_rating=rating,
            irrelevant_analysis=irrelevant_analysis
        )
```

---

## Part 3: RAGAS Score Synthesis

```python
"""
Combine individual metrics into RAGAS score
Weighted average: 25% each for balanced view
"""

from dataclasses import dataclass, field
from enum import Enum

class QualityTier(Enum):
    """Quality categorization"""
    EXCELLENT = "excellent"  # > 0.85
    GOOD = "good"  # 0.75-0.85
    FAIR = "fair"  # 0.60-0.75
    POOR = "poor"  # < 0.60

@dataclass
class EvaluationResult:
    """
    OUTPUT: Complete evaluation result
    """
    query_id: str
    response_id: str
    
    # Individual metric scores
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    
    # Synthesis
    ragas_score: float  # Weighted average
    quality_tier: QualityTier
    
    # Diagnostics
    component_attribution: str  # "retriever", "generator", "both", "ok"
    root_cause: str  # Human-readable diagnosis
    
    # Feedback for improvement
    suggested_improvements: List[str] = field(default_factory=list)
    
    # User feedback (collected later)
    user_rating: Optional[float] = None  # 1-5 stars
    user_feedback: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    evaluation_latency_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)

class RAGASScorer:
    """
    Synthesizes individual metrics into RAGAS score
    """
    
    # Weighting strategy (equal weights = balanced view)
    WEIGHTS = {
        "faithfulness": 0.25,
        "answer_relevancy": 0.25,
        "context_precision": 0.25,
        "context_recall": 0.25
    }
    
    def calculate_ragas_score(
        self,
        faithfulness: float,
        answer_relevancy: float,
        context_precision: float,
        context_recall: float
    ) -> tuple[float, QualityTier]:
        """
        Calculate RAGAS score as weighted average
        
        CONTRACT:
        - Input: 4 individual metric scores (0.0-1.0)
        - Output: RAGAS score (0.0-1.0) + quality tier
        """
        
        # Weighted average
        ragas_score = (
            self.WEIGHTS["faithfulness"] * faithfulness +
            self.WEIGHTS["answer_relevancy"] * answer_relevancy +
            self.WEIGHTS["context_precision"] * context_precision +
            self.WEIGHTS["context_recall"] * context_recall
        )
        
        # Categorize
        if ragas_score > 0.85:
            tier = QualityTier.EXCELLENT
        elif ragas_score > 0.75:
            tier = QualityTier.GOOD
        elif ragas_score > 0.60:
            tier = QualityTier.FAIR
        else:
            tier = QualityTier.POOR
        
        return ragas_score, tier
    
    def diagnose_issues(
        self,
        faithfulness: float,
        answer_relevancy: float,
        context_precision: float,
        context_recall: float
    ) -> tuple[str, str, List[str]]:
        """
        Identify root cause and suggest improvements
        
        LOGIC:
        - Low faithfulness + high relevancy → Generator makes up facts
        - Low relevancy + high faithfulness → Generator ignores context
        - Low precision → Retriever returns too much noise
        - Low recall → Retriever misses key documents
        """
        
        issues = []
        attribution = "ok"
        
        # Retriever diagnostics
        if context_recall < 0.7:
            issues.append("Retriever missing key documents (low context recall)")
            attribution = "retriever"
        
        if context_precision < 0.7:
            issues.append("Retriever returning too much noise (low context precision)")
            attribution = "retriever"
        
        # Generator diagnostics
        if faithfulness < 0.8:
            issues.append("Generator hallucinating facts not in context")
            if attribution == "ok":
                attribution = "generator"
            else:
                attribution = "both"
        
        if answer_relevancy < 0.8:
            issues.append("Generator not addressing the user's question")
            if attribution == "ok":
                attribution = "generator"
            else:
                attribution = "both"
        
        # Generate root cause summary
        if attribution == "retriever":
            root_cause = "Issue is with retrieval: improve query → chunks mapping"
        elif attribution == "generator":
            root_cause = "Issue is with generation: improve prompt or model"
        elif attribution == "both":
            root_cause = "Both retrieval and generation need improvement"
        else:
            root_cause = "System performing well"
        
        # Suggestions
        suggestions = []
        
        if context_recall < 0.7:
            suggestions.append("Improve retrieval: use hybrid search (dense+sparse)")
            suggestions.append("Increase top_k retrieved chunks")
            suggestions.append("Review chunking strategy (may be too small)")
        
        if context_precision < 0.7:
            suggestions.append("Add metadata filtering to retrieval")
            suggestions.append("Use reranking to filter irrelevant chunks")
            suggestions.append("Review embedding model quality")
        
        if faithfulness < 0.8:
            suggestions.append("Update system prompt to emphasize context-only")
            suggestions.append("Add explicit instruction: 'Only use provided context'")
            suggestions.append("Use lower temperature (0.0-0.3) for factual questions")
        
        if answer_relevancy < 0.8:
            suggestions.append("Add query clarification step")
            suggestions.append("Include user intent in system prompt")
            suggestions.append("Use few-shot examples of good answers")
        
        return attribution, root_cause, suggestions
```

---

## Part 4: Evaluation Service (Orchestration)

```python
"""
Main Evaluation Service tying all components together
"""

from typing import Optional
import time

class EvaluationService:
    """
    Orchestrates full evaluation pipeline
    """
    
    def __init__(self):
        self.faithfulness_eval = FaithfulnessEvaluator()
        self.relevancy_eval = AnswerRelevancyEvaluator()
        self.precision_eval = ContextPrecisionEvaluator()
        self.recall_eval = ContextRecallEvaluator()
        self.ragas_scorer = RAGASScorer()
    
    async def evaluate(
        self,
        query: str,
        generated_response: str,
        retrieved_chunks: List[str],
        ideal_chunks: Optional[List[str]] = None,
        query_id: str = None,
        response_id: str = None
    ) -> EvaluationResult:
        """
        Full evaluation pipeline
        
        CONTRACT:
        - Input: query, response, retrieved chunks (+ optional ideal chunks)
        - Output: Complete EvaluationResult with RAGAS score
        - Time: ~20-30s total (4 LLM calls + synthesis)
        
        STEPS:
        1. Evaluate faithfulness (is answer grounded?)
        2. Evaluate answer relevancy (does it address query?)
        3. Evaluate context precision (is retrieved context good?)
        4. Evaluate context recall (did retriever find everything?) [optional]
        5. Calculate RAGAS score
        6. Diagnose root cause
        7. Generate feedback
        """
        
        start_time = time.time()
        context_text = "\n\n".join(retrieved_chunks)
        
        # Parallel evaluation (faster than sequential)
        faithfulness_task = self.faithfulness_eval.evaluate_faithfulness(
            generated_response, retrieved_chunks
        )
        relevancy_task = self.relevancy_eval.evaluate_relevancy(
            query, generated_response, context_text
        )
        precision_task = self.precision_eval.evaluate_context_precision(
            query, retrieved_chunks
        )
        
        # Recall optional (requires ground truth)
        recall_score = 1.0  # Default: assume all relevant chunks retrieved
        if ideal_chunks:
            recall_task = self.recall_eval.evaluate_context_recall(
                retrieved_chunks, ideal_chunks
            )
            recall_result = await recall_task
            recall_score = recall_result.score
        
        # Wait for parallel tasks
        faithfulness_result = await faithfulness_task
        relevancy_result = await relevancy_task
        precision_result = await precision_task
        
        # Extract scores
        faith_score = faithfulness_result.score
        relev_score = relevancy_result.score
        prec_score = precision_result.score
        
        # Calculate RAGAS score
        ragas_score, quality_tier = self.ragas_scorer.calculate_ragas_score(
            faith_score, relev_score, prec_score, recall_score
        )
        
        # Diagnose issues
        attribution, root_cause, suggestions = self.ragas_scorer.diagnose_issues(
            faith_score, relev_score, prec_score, recall_score
        )
        
        # Build result
        evaluation_latency = (time.time() - start_time) * 1000
        
        result = EvaluationResult(
            query_id=query_id or str(uuid4()),
            response_id=response_id or str(uuid4()),
            faithfulness=faith_score,
            answer_relevancy=relev_score,
            context_precision=prec_score,
            context_recall=recall_score,
            ragas_score=ragas_score,
            quality_tier=quality_tier,
            component_attribution=attribution,
            root_cause=root_cause,
            suggested_improvements=suggestions,
            evaluation_latency_ms=evaluation_latency,
            metadata={
                "hallucinated_claims": faithfulness_result.hallucinated_claims,
                "irrelevant_chunks": precision_result.irrelevant_analysis
            }
        )
        
        logger.info(
            f"[EVAL] RAGAS Score: {ragas_score:.2f} ({quality_tier.value}), "
            f"Faith: {faith_score:.2f}, Relev: {relev_score:.2f}, "
            f"Prec: {prec_score:.2f}, Recall: {recall_score:.2f}, "
            f"Attribution: {attribution}, Latency: {evaluation_latency:.0f}ms"
        )
        
        return result
```

---

## Part 5: Feedback Loop Integration

### 5.1 Feeding Back to Data Layer

```python
"""
Update chunk quality scores based on evaluation results
"""

async def feed_back_to_data_layer(
    evaluation_result: EvaluationResult,
    citations: List[Citation],
    data_layer
):
    """
    Update Data Layer with quality signals
    
    LOGIC:
    - If evaluation scored HIGH: chunks used were good
    - If evaluation scored LOW: either bad chunks or bad generation
    - If precision low: irrelevant chunks lowered this retrieval
    """
    
    quality_updates = []
    
    # Case 1: Good response - boost cited chunks
    if evaluation_result.quality_tier in [QualityTier.EXCELLENT, QualityTier.GOOD]:
        for citation in citations:
            quality_updates.append({
                "chunk_id": citation.chunk_id,
                "quality_score_delta": +0.05,  # Boost by 5%
                "reason": "Used in high-quality response"
            })
    
    # Case 2: Low precision - penalize irrelevant chunks
    elif "context_precision" in evaluation_result.metadata:
        irrelevant_chunks = evaluation_result.metadata.get("irrelevant_chunks", [])
        for irrelevant in irrelevant_chunks:
            quality_updates.append({
                "chunk_id": irrelevant.get("chunk_id"),
                "quality_score_delta": -0.1,
                "reason": "Marked as irrelevant by evaluator"
            })
    
    # Send updates
    if quality_updates:
        await data_layer.update_chunk_quality_scores(quality_updates)
        logger.info(f"[EVAL→DATA] Sent {len(quality_updates)} quality updates")
```

### 5.2 Feeding Back to Generation Layer

```python
"""
Provide generation layer with diagnostic feedback
"""

async def feed_back_to_generation_layer(
    evaluation_result: EvaluationResult,
    generation_layer
):
    """
    Update generation with feedback for next iteration
    """
    
    feedback = {
        "query_id": evaluation_result.query_id,
        "ragas_score": evaluation_result.ragas_score,
        "faithfulness": evaluation_result.faithfulness,
        "issues": evaluation_result.suggested_improvements
    }
    
    # If hallucination detected, increase temperature constraint
    if evaluation_result.faithfulness < 0.8:
        feedback["next_temperature"] = 0.0  # Force deterministic
        feedback["prompt_hint"] = "Add: 'Only use the provided context'"
    
    # If relevancy low, adjust quality_critical flag
    if evaluation_result.answer_relevancy < 0.8:
        feedback["quality_critical"] = True  # Use better model next time
    
    await generation_layer.apply_feedback(feedback)
```

---

## Part 6: Production Monitoring & Dashboards

```python
"""
Real-time monitoring with LangSmith integration
"""

class ProductionMonitor:
    """
    Tracks RAGAS scores over time and creates dashboards
    """
    
    def __init__(self):
        self.langsmith_client = Client()  # LangSmith client
        self.metrics_db = Database("rag_metrics")  # PostgreSQL
    
    async def log_evaluation(
        self,
        evaluation_result: EvaluationResult,
        query: str,
        response: str,
        user_id: str
    ):
        """
        Log evaluation result for dashboarding
        """
        
        # Store in PostgreSQL for dashboards
        await self.metrics_db.insert("evaluation_metrics", {
            "query_id": evaluation_result.query_id,
            "response_id": evaluation_result.response_id,
            "user_id": user_id,
            "ragas_score": evaluation_result.ragas_score,
            "faithfulness": evaluation_result.faithfulness,
            "answer_relevancy": evaluation_result.answer_relevancy,
            "context_precision": evaluation_result.context_precision,
            "context_recall": evaluation_result.context_recall,
            "quality_tier": evaluation_result.quality_tier.value,
            "component_attribution": evaluation_result.component_attribution,
            "evaluation_latency_ms": evaluation_result.evaluation_latency_ms,
            "created_at": evaluation_result.created_at
        })
        
        # Log to LangSmith for tracing
        with self.langsmith_client.traced(name="evaluation") as run:
            run.add_tags(["evaluation", evaluation_result.quality_tier.value])
            run.add_metadata({
                "ragas_score": evaluation_result.ragas_score,
                "faithfulness": evaluation_result.faithfulness,
                "answer_relevancy": evaluation_result.answer_relevancy,
                "context_precision": evaluation_result.context_precision,
                "context_recall": evaluation_result.context_recall,
                "root_cause": evaluation_result.root_cause
            })
            run.add_feedback_record(
                key="evaluation_ragas",
                value=evaluation_result.ragas_score
            )
    
    async def check_quality_alerts(self, evaluation_result: EvaluationResult):
        """
        Check if evaluation triggers alerts
        """
        
        alerts = []
        
        # Check thresholds
        if evaluation_result.ragas_score < 0.60:
            alerts.append({
                "severity": "critical",
                "message": f"RAGAS score below threshold: {evaluation_result.ragas_score:.2f}",
                "component": evaluation_result.component_attribution
            })
        
        if evaluation_result.faithfulness < 0.80:
            alerts.append({
                "severity": "high",
                "message": f"High hallucination rate: {1 - evaluation_result.faithfulness:.1%}",
                "component": "generator"
            })
        
        if evaluation_result.context_precision < 0.70:
            alerts.append({
                "severity": "medium",
                "message": f"Low context precision: {evaluation_result.context_precision:.2f}",
                "component": "retriever"
            })
        
        # Send alerts
        for alert in alerts:
            logger.warning(f"[ALERT] {alert['severity'].upper()}: {alert['message']}")
            # Could integrate with Slack/PagerDuty here
    
    async def get_dashboard_metrics(self, period: str = "24h") -> Dict:
        """
        Get metrics for dashboard visualization
        """
        
        results = await self.metrics_db.query(f"""
            SELECT 
                AVG(ragas_score) as avg_ragas,
                AVG(faithfulness) as avg_faithfulness,
                AVG(answer_relevancy) as avg_relevancy,
                AVG(context_precision) as avg_precision,
                AVG(context_recall) as avg_recall,
                COUNT(*) as total_queries,
                SUM(CASE WHEN quality_tier = 'excellent' THEN 1 ELSE 0 END) as excellent_count,
                SUM(CASE WHEN quality_tier = 'poor' THEN 1 ELSE 0 END) as poor_count
            FROM evaluation_metrics
            WHERE created_at > NOW() - INTERVAL '{period}'
        """)
        
        return results[0] if results else {}
```

---

## Part 7: User Feedback Collection

```python
"""
Collect explicit user ratings and implicit signals
"""

@dataclass
class UserFeedback:
    query_id: str
    response_id: str
    user_id: str
    
    # Explicit feedback
    rating: float  # 1-5 stars
    feedback_text: Optional[str]
    
    # Implicit signals
    response_time_to_feedback: float  # How quickly user rated
    query_resubmitted: bool  # Did user ask again? (bad response)
    response_copied: bool  # Did user copy response?
    
    created_at: datetime = field(default_factory=datetime.utcnow)

class FeedbackCollector:
    """
    Collects and processes user feedback
    """
    
    async def collect_explicit_feedback(
        self,
        query_id: str,
        response_id: str,
        user_id: str,
        rating: float,
        feedback_text: str
    ) -> UserFeedback:
        """
        Store explicit user feedback (UI thumbs-up/thumbs-down + comment)
        """
        
        feedback = UserFeedback(
            query_id=query_id,
            response_id=response_id,
            user_id=user_id,
            rating=rating,
            feedback_text=feedback_text,
            response_time_to_feedback=0,  # Calculated by UI
            query_resubmitted=False,
            response_copied=False
        )
        
        # Store in database
        await Database("rag_metrics").insert("user_feedback", {
            "query_id": query_id,
            "response_id": response_id,
            "user_id": user_id,
            "rating": rating,
            "feedback_text": feedback_text,
            "created_at": feedback.created_at
        })
        
        logger.info(f"[FEEDBACK] User {user_id} rated {rating}/5: {feedback_text[:50]}")
        
        return feedback
    
    async def track_implicit_signals(
        self,
        query_id: str,
        signal_type: str,  # "resubmit", "copy", "time_to_feedback"
        value: Any
    ):
        """
        Track implicit quality signals (user behavior)
        """
        
        if signal_type == "resubmit":
            # User asked similar question again = bad response
            logger.warning(f"[SIGNAL] Query {query_id} resubmitted - response may be low quality")
        
        elif signal_type == "copy":
            # User copied response = probably liked it
            logger.info(f"[SIGNAL] Query {query_id} response copied")
        
        # Store signal
        await Database("rag_metrics").insert("implicit_signals", {
            "query_id": query_id,
            "signal_type": signal_type,
            "value": value,
            "created_at": datetime.utcnow()
        })
```

---

## Part 8: Synthetic Dataset Generation

```python
"""
Automatically generate test data from documents
"""

class SyntheticDataGenerator:
    """
    Creates synthetic Q&A pairs for evaluation
    """
    
    def __init__(self):
        self.generation_llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_synthetic_qa_pairs(
        self,
        documents: List[str],
        num_questions_per_doc: int = 3
    ) -> List[Dict]:
        """
        Generate synthetic Q&A pairs from documents
        
        CONTRACT:
        - Input: documents to learn from
        - Output: List of {query, ideal_answer, ideal_chunks}
        - Use: Build evaluation dataset without manual annotation
        """
        
        qa_pairs = []
        
        for doc in documents:
            # Generate questions about this document
            gen_prompt = f"""Generate {num_questions_per_doc} diverse questions that can be answered using this document.

DOCUMENT:
{doc[:2000]}  # Limit to first 2000 chars

Requirements:
1. Questions should be specific and require reading the document
2. Avoid yes/no questions
3. Mix of detail questions and big-picture questions

Format as JSON:
{{
  "questions": ["question 1", "question 2", ...]
}}"""
            
            response = await self.generation_llm.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": gen_prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            try:
                data = json.loads(response.choices[0].message.content)
                questions = data.get("questions", [])
            except:
                questions = []
            
            # For each question, generate ideal answer
            for question in questions:
                answer_prompt = f"""Based on this document, provide a comprehensive answer to the question.

DOCUMENT:
{doc}

QUESTION: {question}

Provide a detailed answer using only information from the document."""
                
                answer_response = await self.generation_llm.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": answer_prompt}],
                    temperature=0.0,
                    max_tokens=500
                )
                
                ideal_answer = answer_response.choices[0].message.content
                
                qa_pairs.append({
                    "query": question,
                    "ideal_answer": ideal_answer,
                    "ideal_chunks": [doc],  # Simplified: whole doc is needed
                    "difficulty": "medium"
                })
        
        logger.info(f"[SYNTH] Generated {len(qa_pairs)} synthetic Q&A pairs")
        
        return qa_pairs
```

---

## Part 9: Integration Points (LEGO Fitting)

### 9.1 Generation → Evaluation

```python
# After generation completes
generated_response: GeneratedResponse = await generation_service.generate(request)

# Immediately evaluate
evaluation_result = await evaluation_service.evaluate(
    query=request.original_query,
    generated_response=generated_response.text,
    retrieved_chunks=[c.content for c in request.retrieved_chunks],
    query_id=request.query_id,
    response_id=generated_response.response_id
)

# Log to monitoring
await production_monitor.log_evaluation(
    evaluation_result=evaluation_result,
    query=request.original_query,
    response=generated_response.text,
    user_id=request.user_id
)

# Check for alerts
await production_monitor.check_quality_alerts(evaluation_result)
```

### 9.2 Evaluation → Data Layer Feedback

```python
# If retrieval quality low, feed back to Data Layer
if evaluation_result.component_attribution == "retriever":
    await feed_back_to_data_layer(
        evaluation_result,
        generated_response.citations,
        data_layer
    )
```

### 9.3 Evaluation → Generation Feedback

```python
# If generation quality low, provide feedback for next iteration
if evaluation_result.quality_tier == QualityTier.POOR:
    await feed_back_to_generation_layer(
        evaluation_result,
        generation_service
    )
```

### 9.4 Evaluation → UI (User Feedback Collection)

```javascript
// React frontend shows quality indicator + feedback form
<ResponseCard 
    response={response}
    ragas_score={evaluation.ragas_score}
    quality_tier={evaluation.quality_tier}
    onRating={(rating, feedback) => {
        // Send user feedback back to evaluation service
        await api.post('/feedback', {
            response_id: response.response_id,
            rating: rating,
            feedback_text: feedback
        });
    }}
/>
```

---

## Part 10: Configuration

```yaml
# evaluation_config.yaml
evaluation:
  # RAGAS Metrics Configuration
  metrics:
    faithfulness:
      enabled: true
      threshold: 0.80  # Alert if < 0.8
      cost_estimate: "$0.003 per evaluation"
    
    answer_relevancy:
      enabled: true
      threshold: 0.80
      cost_estimate: "$0.002 per evaluation"
    
    context_precision:
      enabled: true
      threshold: 0.70
      max_chunks_to_eval: 10  # Evaluate top-10 for cost
      cost_estimate: "$0.002 per evaluation"
    
    context_recall:
      enabled: false  # Requires ground truth
      threshold: 0.85
  
  # RAGAS Score Calculation
  ragas_weights:
    faithfulness: 0.25
    answer_relevancy: 0.25
    context_precision: 0.25
    context_recall: 0.25
  
  quality_thresholds:
    excellent: 0.85
    good: 0.75
    fair: 0.60
    poor: 0.0
  
  # Production Monitoring
  monitoring:
    enabled: true
    alert_threshold_critical: 0.60  # RAGAS < 0.6
    alert_threshold_high: 0.70
    tracking_period: "24h"
    dashboard_refresh_interval: "5m"
  
  # LangSmith Integration
  langsmith:
    enabled: true
    project_name: "rag_evaluation"
    trace_all_evals: true
  
  # User Feedback
  user_feedback:
    collect_explicit: true
    track_implicit_signals: true
    feedback_form_shown: true  # Show 1-5 rating in UI
  
  # Synthetic Dataset Generation
  synthetic_generation:
    enabled: true
    questions_per_document: 3
    regenerate_monthly: true
  
  # Alerting
  alerts:
    channels: ["slack", "email"]  # Where to send alerts
    slack_webhook: ${SLACK_WEBHOOK_URL}
    recipients: ["team@company.com"]
```

---

## Part 11: Performance Targets & SLA

```
EVALUATION LATENCY SLA:

Per-Metric Latency:
  Faithfulness: 2-5s (LLM + claim extraction)
  Answer Relevancy: 1-2s (LLM evaluation)
  Context Precision: 2-5s (evaluates top-10 chunks)
  Context Recall: <100ms (if ground truth available)

Total Evaluation Time:
  Parallel execution: ~5-8s (all metrics run in parallel)
  Sequential would be: ~10-15s

COST PER EVALUATION:

Using GPT-4o-mini for most:
  - Faithfulness: ~$0.003
  - Answer Relevancy: ~$0.002
  - Context Precision: ~$0.002 (10 chunks)
  - Total per evaluation: ~$0.007

For 1000 queries/day:
  - Evaluation cost: ~$7/day = $210/month
  - Way cheaper than finding bad responses in production!

QUALITY TARGETS:

System-Wide:
  - RAGAS score > 0.75 (target median)
  - Hallucination rate < 10% (faithfulness > 0.9)
  - Context precision > 0.80
  - Context recall > 0.85 (if measured)
  - User satisfaction > 4.0/5.0 stars

Per Component:
  - Retriever health: context precision + recall
  - Generator health: faithfulness + relevancy
  - Overall health: RAGAS score

MONITORING DASHBOARD:

Real-Time Metrics:
  - RAGAS score (rolling 24h, 7d, 30d)
  - Metric breakdowns (individual scores)
  - Alert indicators (red/yellow/green)
  - User feedback sentiment
  - Top failing queries (< 0.5 score)
  - Cost per query trend

Distribution Metrics:
  - % Excellent (> 0.85)
  - % Good (0.75-0.85)
  - % Fair (0.60-0.75)
  - % Poor (< 0.60)
```

---

## Part 12: Evaluation Framework as LEGO Brick Summary

Your Evaluation Framework **perfectly fits** because:

✅ **Standardized Input**: Accepts exact GeneratedResponse from Generation Layer
✅ **Multi-Metric Assessment**: 4-dimension evaluation prevents gaming metrics
✅ **Component Attribution**: Clearly identifies if problem is retriever or generator
✅ **Feedback-Driven**: Signals flow back to Data Layer, Generation Layer, and Retrieval
✅ **Production Observable**: LangSmith integration + real-time dashboards
✅ **User-Centric**: Collects explicit ratings + implicit behavior signals
✅ **No Ground Truth Required**: RAGAS metrics work reference-free
✅ **Synthetic Data Generation**: Auto-creates evaluation dataset from documents
✅ **Continuous Improvement**: Feedback loops enable iterative optimization

**The Pipeline Fits Because**:
- Generation produces response → Evaluation scores it
- Low scores → Diagnostic feedback flows back
- Hallucinations detected → Generation layer tunes prompt
- Irrelevant chunks found → Data Layer downgrades chunk quality
- Missing chunks identified → Retrieval strategy adjusted
- User feedback collected → Ground truth for future evals
- Dashboard shows trends → PMs see quality over time

**Key Benefits**:
1. **Catches problems before users**: Evaluate every response, not just samples
2. **Component-level diagnostics**: Spend effort where it matters most
3. **Feedback loops**: System improves continuously, not episodically
4. **Cost-effective**: LLM-based evaluation ~$0.007/response
5. **Production-grade**: Monitoring, alerting, A/B testing ready

**Next Implementation Steps**:
1. Set up RAGAS metrics (start with faithfulness + precision)
2. Build EvaluationService with parallel metric execution
3. Integrate with LangSmith for tracing
4. Create monitoring dashboard (metrics → PostgreSQL)
5. Add user feedback UI component
6. Implement synthetic dataset generation
7. Set up alerting (Slack integration)
8. A/B test metric thresholds against manual quality assessment
9. Deploy feedback loops to Data/Generation layers
10. Monitor and tune weights over 2-4 weeks in production

**Metric Recommendations by Use Case**:

| Use Case | Priority Metrics | Threshold |
|----------|------------------|-----------|
| Medical/Legal | Faithfulness > Relevancy | > 0.95 |
| Customer Support | Relevancy > Faithfulness | > 0.85 |
| Code Generation | Faithfulness + Correctness | > 0.90 |
| Content Generation | Relevancy > Faithfulness | > 0.80 |
| Technical Q&A | All equal | > 0.85 |
