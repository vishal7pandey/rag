from backend.core.chunkers.recursive_chunker import RecursiveChunker


def test_recursive_chunker_splits_on_paragraph() -> None:
    """Paragraphs preserved as chunk boundaries when separator present."""

    chunker = RecursiveChunker()
    text = "Para 1.\n\nPara 2.\n\nPara 3."

    chunks = chunker.chunk(
        text,
        chunk_size=100,
        separators=["\n\n", "\n", "."],
        keep_separator=False,
    )

    contents = [c["content"] for c in chunks]
    assert len(chunks) >= 3
    assert any("Para 1" in c for c in contents)
    assert any("Para 2" in c for c in contents)


def test_recursive_chunker_tries_separators_in_order() -> None:
    """Falls back to next separator when earlier ones do not split."""

    chunker = RecursiveChunker()
    text = "Sentence 1. Sentence 2. Sentence 3." * 20

    chunks = chunker.chunk(
        text,
        chunk_size=100,
        separators=["NONEXISTENT", ".", " "],
        keep_separator=False,
    )

    assert chunks
    for chunk in chunks:
        assert len(chunk["content"]) <= 150


def test_recursive_chunker_keeps_separator() -> None:
    """keep_separator=True retains separators in the resulting chunks."""

    chunker = RecursiveChunker()
    text = "A. B. C."

    chunks_with = chunker.chunk(
        text,
        chunk_size=100,
        separators=["."],
        keep_separator=True,
    )
    chunks_without = chunker.chunk(
        text,
        chunk_size=100,
        separators=["."],
        keep_separator=False,
    )

    assert chunks_with
    assert chunks_without
    # With separator, chunks should tend to contain "." characters
    assert any("." in c["content"] for c in chunks_with)


def test_recursive_chunker_handles_no_separators() -> None:
    """Falls back to char-level split if no separator works."""

    chunker = RecursiveChunker()
    text = "nosecondboundaryhere" * 10

    chunks = chunker.chunk(
        text,
        chunk_size=50,
        separators=["\n\n", "\n"],
        keep_separator=False,
    )

    assert len(chunks) > 1
    assert all(len(c["content"]) <= 60 for c in chunks)
