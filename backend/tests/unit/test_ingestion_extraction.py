from uuid import uuid4

from backend.api.schemas import IngestionResponse, IngestionStatus, UploadedFileInfo
from backend.core.ingestion_extraction import (
    IngestionExtractionService,
    get_extracted_document,
)


def test_run_extraction_for_ingestion_single_txt_file() -> None:
    """IngestionExtractionService links ingestion metadata to extracted text."""

    ingestion_id = uuid4()
    document_id = uuid4()

    ingestion = IngestionResponse(
        ingestion_id=ingestion_id,
        status=IngestionStatus.PENDING,
        document_id=document_id,
        files=[
            UploadedFileInfo(
                filename="doc.txt",
                file_size_mb=0.001,
                mime_type="text/plain",
            )
        ],
    )

    file_bytes = {"doc.txt": b"Hello from ingestion extraction service"}

    service = IngestionExtractionService()
    docs = service.run_extraction_for_ingestion(ingestion, file_bytes)

    assert len(docs) == 1
    extracted = docs[0]

    # The extracted document should be stored and linked by document_id.
    assert extracted.document_id == document_id
    stored = get_extracted_document(document_id)
    assert stored is not None
    assert stored.document_id == document_id
    assert any("Hello" in page.raw_text for page in stored.pages)


def test_run_extraction_for_ingestion_multiple_files() -> None:
    """Multiple files in an ingestion produce multiple extracted documents."""

    ingestion_id = uuid4()
    primary_document_id = uuid4()

    ingestion = IngestionResponse(
        ingestion_id=ingestion_id,
        status=IngestionStatus.PENDING,
        document_id=primary_document_id,
        files=[
            UploadedFileInfo(
                filename="doc1.txt",
                file_size_mb=0.001,
                mime_type="text/plain",
            ),
            UploadedFileInfo(
                filename="doc2.txt",
                file_size_mb=0.001,
                mime_type="text/plain",
            ),
            UploadedFileInfo(
                filename="doc3.txt",
                file_size_mb=0.001,
                mime_type="text/plain",
            ),
        ],
    )

    file_bytes = {
        "doc1.txt": b"First document",
        "doc2.txt": b"Second document",
        "doc3.txt": b"Third document",
    }

    service = IngestionExtractionService()
    docs = service.run_extraction_for_ingestion(ingestion, file_bytes)

    # Should have an ExtractedDocument per file.
    assert len(docs) == 3

    doc_ids = {doc.document_id for doc in docs}
    # The primary ingestion document_id should be used for the first document.
    assert primary_document_id in doc_ids

    # All resulting document_ids should be present in the store.
    for doc_id in doc_ids:
        stored = get_extracted_document(doc_id)
        assert stored is not None
        assert stored.document_id == doc_id
