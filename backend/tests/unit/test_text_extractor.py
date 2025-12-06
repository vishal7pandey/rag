from uuid import uuid4

from backend.core.extractors.text_extractor import TextExtractor


def test_text_extractor_reads_utf8() -> None:
    extractor = TextExtractor()
    content = "Hello World\nLine 2\nLine 3".encode("utf-8")

    result = extractor.extract(
        content,
        document_id=uuid4(),
        filename="test.txt",
    )

    assert result.total_pages >= 1
    text = result.pages[0].raw_text
    assert "Hello World" in text
    assert "Line 2" in text

    meta = result.extraction_metadata
    assert meta["total_words"] == sum(p.word_count for p in result.pages)
    assert meta["total_chars"] == sum(p.char_count for p in result.pages)
    assert meta["empty_pages"] + meta["non_empty_pages"] == result.total_pages


def test_text_extractor_handles_encoding_detection() -> None:
    extractor = TextExtractor()
    content = "Héllo Wörld".encode("latin-1")

    result = extractor.extract(
        content,
        document_id=uuid4(),
        filename="test.txt",
    )

    text = result.pages[0].raw_text
    assert len(text) > 0


def test_text_extractor_groups_lines_into_pages() -> None:
    extractor = TextExtractor()
    lines = [f"Line {i}" for i in range(1000)]
    content = "\n".join(lines).encode("utf-8")

    result = extractor.extract(
        content,
        document_id=uuid4(),
        filename="large.txt",
    )

    assert result.total_pages > 1
