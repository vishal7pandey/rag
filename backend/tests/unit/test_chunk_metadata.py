from uuid import uuid4

from backend.core.chunking_metadata import ChunkMetadataTracker


def test_chunk_creation_with_metadata() -> None:
    """Chunk created with full metadata and counts."""

    doc_id = uuid4()
    chunk = ChunkMetadataTracker.create_chunk(
        content="This is chunk content",
        document_id=doc_id,
        page_number=0,
        position_in_page={"start": 0, "end": 100},
        section_title="Introduction",
        original_content="This is chunk content",
        document_type="txt",
        source_filename="doc.txt",
        language="en",
    )

    assert chunk.document_id == doc_id
    assert chunk.metadata["page_number"] == 0
    assert chunk.metadata["position_in_page"]["start"] == 0
    assert chunk.metadata["section_title"] == "Introduction"
    assert chunk.word_count == 4
    assert chunk.char_count == len("This is chunk content")


def test_chunk_quality_score_calculation() -> None:
    """Quality score reflects chunk size (medium better than tiny)."""

    good_chunk = ChunkMetadataTracker.create_chunk(
        content=" ".join(["word"] * 100),
        document_id=uuid4(),
        page_number=0,
        position_in_page={"start": 0, "end": 500},
        section_title=None,
        original_content=None,
        document_type="txt",
        source_filename="doc.txt",
        language="en",
    )

    small_chunk = ChunkMetadataTracker.create_chunk(
        content="tiny",
        document_id=uuid4(),
        page_number=0,
        position_in_page={"start": 0, "end": 4},
        section_title=None,
        original_content=None,
        document_type="txt",
        source_filename="doc.txt",
        language="en",
    )

    assert good_chunk.quality_score > small_chunk.quality_score


def test_chunk_token_count_estimation() -> None:
    """Token count approximated as 1.3x word count."""

    chunk = ChunkMetadataTracker.create_chunk(
        content="word " * 100,
        document_id=uuid4(),
        page_number=0,
        position_in_page={"start": 0, "end": 500},
        section_title=None,
        original_content=None,
        document_type="txt",
        source_filename="doc.txt",
        language="en",
    )

    assert chunk.token_count == 130
