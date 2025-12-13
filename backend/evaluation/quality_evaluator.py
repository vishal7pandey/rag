from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional


@dataclass
class EvaluationMetric:
    trace_id: str
    feedback_id: str
    faithfulness: float
    relevance: float
    completeness: float
    citation_accuracy: float
    overall_score: float
    user_feedback: Optional[bool] = None
    user_rating: Optional[int] = None
    document_refs: List[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "traceId": self.trace_id,
            "feedbackId": self.feedback_id,
            "faithfulness": self.faithfulness,
            "relevance": self.relevance,
            "completeness": self.completeness,
            "citationAccuracy": self.citation_accuracy,
            "overallScore": self.overall_score,
            "userFeedback": self.user_feedback,
            "userRating": self.user_rating,
            "documents": self.document_refs or [],
        }


class QualityEvaluator:
    def evaluate(
        self,
        *,
        trace_id: str,
        feedback_id: str,
        artifacts: List[Dict[str, Any]],
        user_feedback: Optional[bool] = None,
        user_rating: Optional[int] = None,
    ) -> EvaluationMetric:
        normalized = [self._normalize_artifact(a) for a in artifacts]

        query_text = self._get_query_text(normalized)
        answer_text = self._get_answer_text(normalized)
        chunks_text = self._get_chunks_text(normalized)

        faithfulness = self._compute_faithfulness(answer_text, chunks_text)
        relevance = self._compute_relevance(query_text, chunks_text)
        completeness = self._compute_completeness(query_text, answer_text)
        citation_accuracy = self._compute_citation_accuracy(normalized)
        document_refs = self._extract_document_refs(normalized)

        overall_score = (
            faithfulness * 0.4
            + relevance * 0.3
            + completeness * 0.2
            + citation_accuracy * 0.1
        )

        return EvaluationMetric(
            trace_id=trace_id,
            feedback_id=feedback_id,
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            citation_accuracy=citation_accuracy,
            overall_score=overall_score,
            user_feedback=user_feedback,
            user_rating=user_rating,
            document_refs=document_refs,
        )

    def _normalize_artifact(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        # PostgresArtifactStorage returns {type, data, timestamp}; InMemory uses {type, data}
        if "data" in entry and isinstance(entry.get("data"), dict):
            data = entry["data"].copy()
            if "type" not in data and "type" in entry:
                data["type"] = entry["type"]
            return data
        return entry

    def _get_query_text(self, artifacts: List[Dict[str, Any]]) -> str:
        for a in artifacts:
            if a.get("type") == "query":
                return str(a.get("query_text") or "")
        return ""

    def _get_answer_text(self, artifacts: List[Dict[str, Any]]) -> str:
        for a in artifacts:
            if a.get("type") == "answer":
                return str(a.get("answer_text") or "")
        # fallback
        for a in artifacts:
            if a.get("type") == "response":
                return str(a.get("answer_preview") or "")
        return ""

    def _get_chunks_text(self, artifacts: List[Dict[str, Any]]) -> str:
        for a in artifacts:
            if a.get("type") == "retrieved_chunks":
                chunks = a.get("chunks_data") or []
                parts: List[str] = []
                for c in chunks:
                    if not isinstance(c, dict):
                        continue
                    parts.append(
                        str(c.get("content") or c.get("content_preview") or "")
                    )
                return " ".join(parts)
        return ""

    def _compute_faithfulness(self, answer: str, chunks_text: str) -> float:
        answer_words = self._words(answer)
        if not answer_words:
            return 0.5
        chunk_words = self._words(chunks_text)
        if not chunk_words:
            return 0.5
        overlap = len(answer_words & chunk_words) / float(len(answer_words))
        return max(0.0, min(overlap, 1.0))

    def _compute_relevance(self, query: str, chunks_text: str) -> float:
        query_words = self._words(query)
        if not query_words:
            return 0.5
        chunk_words = self._words(chunks_text)
        if not chunk_words:
            return 0.5
        overlap = len(query_words & chunk_words) / float(len(query_words))
        return max(0.0, min(overlap, 1.0))

    def _compute_completeness(self, query: str, answer: str) -> float:
        if not answer.strip():
            return 0.2
        query_len = len(query.split())
        answer_len = len(answer.split())
        if query_len <= 0:
            return 0.6
        if answer_len < max(2, query_len // 2):
            return 0.4
        if answer_len > query_len * 20:
            return 0.6
        return 0.8

    def _compute_citation_accuracy(self, artifacts: List[Dict[str, Any]]) -> float:
        answer = ""
        citation_map: Dict[int, Any] | None = None

        for a in artifacts:
            if a.get("type") == "answer" and isinstance(a.get("answer_text"), str):
                answer = a.get("answer_text") or ""
            if a.get("type") == "prompt" and isinstance(a.get("citation_map"), dict):
                citation_map = a.get("citation_map")

        if not answer.strip():
            return 0.5
        if not citation_map:
            return 0.5

        cited = {int(m.group(1)) for m in re.finditer(r"\[Source (\d+)\]", answer)}
        if not cited:
            return 0.5

        valid = {i for i in cited if i in citation_map}
        return max(0.0, min(len(valid) / float(len(cited)), 1.0))

    def _extract_document_refs(
        self, artifacts: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        citation_map: Dict[int, Any] | None = None
        for a in artifacts:
            if a.get("type") == "prompt" and isinstance(a.get("citation_map"), dict):
                citation_map = a.get("citation_map")

        if not citation_map:
            return []

        refs: List[Dict[str, str]] = []
        seen: set[str] = set()

        for _, meta in citation_map.items():
            if not isinstance(meta, dict):
                continue
            doc_id = meta.get("document_id")
            filename = meta.get("source_file") or meta.get("filename")
            if not doc_id and not filename:
                continue
            key = f"{doc_id}|{filename}"
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "documentId": str(doc_id) if doc_id is not None else "",
                    "filename": str(filename) if filename is not None else "",
                }
            )

        return refs

    def _words(self, text: str) -> set[str]:
        return {w for w in (text or "").lower().split() if w}
