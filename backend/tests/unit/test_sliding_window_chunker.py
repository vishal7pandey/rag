from backend.core.chunkers.sliding_window_chunker import SlidingWindowChunker


def test_chunker_creates_basic_chunks() -> None:
    """Basic chunking produces expected fixed-size windows with overlap."""

    chunker = SlidingWindowChunker()
    text = "a" * 1000

    chunks = chunker.chunk(text, chunk_size=100, overlap=10)

    assert len(chunks) > 1
    assert chunks[0]["content"] == "a" * 100
    # Second chunk should overlap previous by 10 characters.
    assert chunks[1]["content"].startswith("a" * 10)


def test_chunker_respects_overlap() -> None:
    """Overlap parameter is respected between consecutive chunks."""

    chunker = SlidingWindowChunker()
    text = "abcdefghijklmnopqrstuvwxyz" * 40  # 1040 chars

    chunks = chunker.chunk(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    for i in range(len(chunks) - 1):
        current = chunks[i]["content"]
        nxt = chunks[i + 1]["content"]
        # Last 20 chars of current should appear at the start of the next.
        assert nxt.startswith(current[-20:])


def test_chunker_handles_short_text() -> None:
    """Short text smaller than chunk_size produces a single chunk."""

    chunker = SlidingWindowChunker()
    text = "Short text"

    chunks = chunker.chunk(text, chunk_size=100, overlap=10)

    assert len(chunks) == 1
    assert chunks[0]["content"] == "Short text"


def test_chunker_handles_empty_text() -> None:
    """Empty text produces no chunks."""

    chunker = SlidingWindowChunker()
    text = ""

    chunks = chunker.chunk(text, chunk_size=100, overlap=10)

    assert len(chunks) == 0


def test_chunker_respects_size_limit() -> None:
    """No chunk exceeds the configured size limit."""

    chunker = SlidingWindowChunker()
    text = "word " * 200  # ~1000 chars

    chunks = chunker.chunk(
        text,
        chunk_size=100,
        overlap=10,
        length_fn=len,
    )

    assert chunks
    for chunk in chunks:
        assert len(chunk["content"]) <= 100
