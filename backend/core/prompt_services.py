from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from backend.core.prompt_models import (
    PromptConstructionRequest,
    PromptConstructionResponse,
)
from backend.core.query_models import RetrievedChunk


class TokenCounter:
    """Approximate token counter for prompt components.

    This implementation uses a simple word-based heuristic so that tests can
    assert basic properties (non-zero counts, relative sizes) without pulling
    in a model-specific tokenizer dependency.
    """

    def __init__(self, model: str = "gpt-5-nano") -> None:
        self._model = model

    def count(self, text: str) -> int:
        """Return an approximate token count for the given text.

        For now this counts whitespace-separated tokens and guarantees at least
        one token for any non-empty string.
        """

        if not text:
            return 0
        return max(1, len(text.split()))

    def count_batch(self, texts: List[str]) -> List[int]:
        """Count tokens for a batch of texts."""

        return [self.count(t) for t in texts]


class TokenBudgetAllocator:
    """Allocate token budget across prompt components.

    This allocator knows about a small set of model context windows and returns
    how many tokens remain available for retrieved context after accounting for
    system prompt, query, conversation history, examples, and reserved response
    budget.
    """

    _CONTEXT_WINDOW_BY_MODEL: Dict[str, int] = {
        "gpt-5-nano": 128_000,
    }

    def _get_context_window_size(self, model: str) -> int:
        return self._CONTEXT_WINDOW_BY_MODEL.get(model, 128_000)

    def allocate(
        self,
        *,
        system_tokens: int,
        query_tokens: int,
        history_tokens: int = 0,
        examples_tokens: int = 0,
        response_budget: int = 1500,
        model: str = "gpt-5-nano",
    ) -> Dict[str, int]:
        """Calculate token budget breakdown for the prompt.

        Raises ValueError if the fixed components exceed the model context
        window.
        """

        context_window = self._get_context_window_size(model)

        total_fixed = (
            system_tokens
            + query_tokens
            + history_tokens
            + examples_tokens
            + response_budget
        )

        if total_fixed > context_window:
            raise ValueError("Token budget exceeds model context window")

        available_for_context = context_window - total_fixed

        return {
            "system_prompt": system_tokens,
            "query": query_tokens,
            "history": history_tokens,
            "examples": examples_tokens,
            "response_reserved": response_budget,
            "available_for_context": available_for_context,
            "total_used": total_fixed,
            "context_window": context_window,
        }


class CitationFormatter:
    """Format retrieved chunks with [Source N] markers and build citation maps."""

    def format_chunk(self, chunk: RetrievedChunk, citation_index: int) -> str:
        """Return a formatted chunk string with a citation marker.

        Example format:
        [Source 1] File: policy.pdf, Page 3
        Content text...
        """

        metadata = chunk.metadata or {}
        source_file = (
            metadata.get("source_file") or metadata.get("filename") or "unknown"
        )
        page = metadata.get("page")
        section = metadata.get("section")

        header_parts = [f"[Source {citation_index}]"]
        if source_file:
            header_parts.append(f"File: {source_file}")
        if page is not None:
            header_parts.append(f"Page {page}")
        if section:
            header_parts.append(section)

        header = ", ".join(header_parts)
        return f"{header}\n{chunk.content}\n"

    def build_citation_map(
        self,
        chunks: List[RetrievedChunk],
        used_indices: List[int],
    ) -> Dict[int, Dict[str, Any]]:
        """Build a citation map {index -> chunk metadata} for used chunks."""

        citation_map: Dict[int, Dict[str, Any]] = {}
        for index, chunk in zip(used_indices, chunks):
            meta: Dict[str, Any] = {
                "chunk_id": str(chunk.chunk_id),
                "document_id": str(chunk.document_id) if chunk.document_id else None,
                "similarity_score": chunk.similarity_score,
            }
            # Include any known source-related metadata as-is.
            meta.update(chunk.metadata or {})
            citation_map[index] = meta
        return citation_map


class ContextAssembler:
    """Pack retrieved chunks into a context string within a token budget."""

    def assemble(
        self,
        chunks: List[RetrievedChunk],
        available_tokens: int,
        token_counter: TokenCounter,
        citation_formatter: CitationFormatter,
    ) -> Tuple[str, List[int], Dict[str, int]]:
        """Assemble context from chunks.

        Returns (context_str, used_citation_indices, metrics).
        """

        if available_tokens <= 0 or not chunks:
            return (
                "",
                [],
                {"context_tokens": 0, "chunks_included": 0, "chunks_truncated": 0},
            )

        # Sort by rank (1 = best). Fallback to similarity_score if needed.
        sorted_chunks = sorted(chunks, key=lambda c: (c.rank, -c.similarity_score))

        remaining = available_tokens
        parts: List[str] = []
        used_indices: List[int] = []
        chunks_included = 0
        chunks_truncated = 0

        for chunk_idx, chunk in enumerate(sorted_chunks, start=1):
            citation_index = len(used_indices) + 1
            formatted = citation_formatter.format_chunk(chunk, citation_index)
            tokens = token_counter.count(formatted)

            if tokens <= remaining:
                parts.append(formatted)
                used_indices.append(citation_index)
                remaining -= tokens
                chunks_included += 1
                continue

            # Try truncation only if we have some budget left.
            if remaining > 0:
                original_text = formatted
                words = original_text.split()
                if not words:
                    break

                # Leave a small buffer for an ellipsis marker.
                max_tokens_for_truncated = max(0, remaining - 1)
                truncated_words = words[:max_tokens_for_truncated] or words[:1]
                truncated_text = " ".join(truncated_words) + " [...]\n"
                truncated_tokens = token_counter.count(truncated_text)

                if truncated_tokens <= remaining:
                    parts.append(truncated_text)
                    used_indices.append(citation_index)
                    remaining -= truncated_tokens
                    chunks_included += 1
                    chunks_truncated += 1
            break

        context_str = "".join(parts)
        context_tokens = token_counter.count(context_str) if context_str else 0

        metrics = {
            "context_tokens": context_tokens,
            "chunks_included": chunks_included,
            "chunks_truncated": chunks_truncated,
        }
        return context_str, used_indices, metrics


class PromptAssembler:
    """High-level orchestrator for prompt construction from retrieved chunks."""

    def __init__(
        self,
        token_counter: TokenCounter | None = None,
        budget_allocator: TokenBudgetAllocator | None = None,
        citation_formatter: CitationFormatter | None = None,
        context_assembler: ContextAssembler | None = None,
    ) -> None:
        self._token_counter = token_counter or TokenCounter()
        self._budget_allocator = budget_allocator or TokenBudgetAllocator()
        self._citation_formatter = citation_formatter or CitationFormatter()
        self._context_assembler = context_assembler or ContextAssembler()

    def _build_system_prompt(self) -> str:
        """Return the default system prompt used for RAG answers."""

        return (
            "You are a helpful, accurate, and concise assistant.\n\n"
            "When answering:\n"
            "1. Use ONLY the provided context to form your answer.\n"
            "2. Cite your sources using [Source N] markers.\n"
            "3. If the context does not contain the answer, say so explicitly.\n"
            "4. Be precise and avoid generalizations."
        )

    def construct_prompt(
        self,
        request: PromptConstructionRequest,
    ) -> PromptConstructionResponse:
        """Assemble a prompt from the given request within a token budget."""

        start = time.time()

        system_prompt = self._build_system_prompt()
        query_text = request.query_text

        system_tokens = self._token_counter.count(system_prompt)
        query_tokens = self._token_counter.count(query_text)
        history_tokens = 0  # Conversation history not yet modeled in detail.
        examples_tokens = 0  # Few-shot examples currently ignored.

        budget = self._budget_allocator.allocate(
            system_tokens=system_tokens,
            query_tokens=query_tokens,
            history_tokens=history_tokens,
            examples_tokens=examples_tokens,
            response_budget=request.max_tokens_for_response,
            model=request.model,
        )

        available_for_context = budget["available_for_context"]

        context_str, used_indices, context_metrics = self._context_assembler.assemble(
            chunks=request.retrieved_chunks,
            available_tokens=available_for_context,
            token_counter=self._token_counter,
            citation_formatter=self._citation_formatter,
        )

        citation_map = self._citation_formatter.build_citation_map(
            request.retrieved_chunks,
            used_indices,
        )

        # Build user message with context + query sections.
        if context_str:
            context_section = f"---RETRIEVED CONTEXT---\n{context_str}\n"
        else:
            context_section = (
                "---RETRIEVED CONTEXT---\n"
                "No relevant context was retrieved. Answer based on general knowledge only if appropriate.\n"
            )

        user_section = f"---USER QUERY---\n{query_text}"
        user_message = f"{context_section}\n{user_section}"

        token_metrics: Dict[str, int] = dict(budget)
        token_metrics.update(context_metrics)

        assembly_latency_ms = (time.time() - start) * 1000.0

        return PromptConstructionResponse(
            request_id=request.request_id,
            system_message=system_prompt,
            user_message=user_message,
            citation_map=citation_map,
            token_metrics=token_metrics,
            chunks_included=context_metrics.get("chunks_included", 0),
            chunks_truncated=context_metrics.get("chunks_truncated", 0),
            assembly_latency_ms=assembly_latency_ms,
        )
