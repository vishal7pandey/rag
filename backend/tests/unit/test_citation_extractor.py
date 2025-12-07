from __future__ import annotations

from backend.core.generation_services import CitationExtractor


def test_extract_single_citation() -> None:
    extractor = CitationExtractor()
    text = "Based on policy [Source 1], remote work is allowed."

    citations = extractor.extract_citations(text)

    assert 1 in citations
    assert len(citations[1]) == 1


def test_extract_multiple_citations() -> None:
    extractor = CitationExtractor()
    text = "Policy [Source 1] states that [Source 2] requires approval."

    citations = extractor.extract_citations(text)

    assert 1 in citations
    assert 2 in citations
    assert len(citations[1]) == 1
    assert len(citations[2]) == 1


def test_extract_no_citations_returns_empty_dict() -> None:
    extractor = CitationExtractor()
    text = "This is an answer with no citations."

    citations = extractor.extract_citations(text)

    assert citations == {}


def test_extract_ignores_malformed_citations() -> None:
    extractor = CitationExtractor()
    text = "[Source ABC] and [source 1] and [Source 1]"

    citations = extractor.extract_citations(text)

    assert 1 in citations
    assert len(citations[1]) == 1
    assert len(citations) == 1
