"""Glue between ingestion metadata and text extraction (Story 007).

This module provides a small service that takes an `IngestionResponse`
plus raw file bytes, runs the text extraction pipeline, and stores the
resulting `ExtractedDocument` instances in an in-memory store.

There are no HTTP endpoints here; this is intended to be called from
background workers or future ingestion orchestration code.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional
from uuid import UUID

from backend.api.schemas import IngestionResponse
from backend.core.data_models import ExtractedDocument
from backend.core.exceptions import ExtractionError
from backend.core.logging import get_logger
from backend.core.text_extraction_service import TextExtractionService


# In-memory store mapping document_id -> ExtractedDocument.
_EXTRACTED_DOCUMENT_STORE: Dict[UUID, ExtractedDocument] = {}


class IngestionExtractionService:
    """Runs text extraction for completed uploads and stores results."""

    def __init__(
        self, extraction_service: Optional[TextExtractionService] = None
    ) -> None:
        self._extraction_service = extraction_service or TextExtractionService()

    def run_extraction_for_ingestion(
        self,
        ingestion: IngestionResponse,
        file_bytes: Mapping[str, bytes],
    ) -> List[ExtractedDocument]:
        """Run text extraction for a given ingestion.

        Parameters
        ----------
        ingestion:
            The ingestion response produced by `/api/ingest/upload`.
        file_bytes:
            Mapping of filename -> raw bytes for each uploaded file.

        Notes
        -----
        For now this implementation assumes a single primary document per
        ingestion and uses the first entry in `ingestion.files` that has a
        corresponding entry in `file_bytes`. Future stories can extend this
        to handle multi-file ingestions explicitly.
        """

        logger = get_logger("rag.core.ingestion_extraction")

        if ingestion.document_id is None:
            raise ValueError("IngestionResponse must have a document_id for extraction")

        if not ingestion.files:
            raise ValueError("IngestionResponse has no files to extract")

        logger.info(
            "ingestion_extraction_started",
            extra={
                "context": {
                    "ingestion_id": str(ingestion.ingestion_id),
                    "document_id": str(ingestion.document_id),
                    "file_count": len(ingestion.files),
                }
            },
        )

        extracted_docs: List[ExtractedDocument] = []

        for index, f in enumerate(ingestion.files):
            if f.filename not in file_bytes:
                continue

            content = file_bytes[f.filename]

            # Use the ingestion-level document_id for the first file, and
            # generate new document_ids for any additional files.
            if index == 0:
                doc_id = ingestion.document_id
            else:
                from uuid import uuid4

                doc_id = uuid4()

            if doc_id is None:
                from uuid import uuid4

                doc_id = uuid4()

            try:
                extracted = self._extraction_service.extract(
                    filename=f.filename,
                    content=content,
                    document_id=doc_id,
                )
            except ExtractionError as exc:
                logger.error(
                    "ingestion_extraction_failed",
                    extra={
                        "context": {
                            "ingestion_id": str(ingestion.ingestion_id),
                            "document_id": str(doc_id),
                            "filename": exc.details.get("filename"),
                            "error_type": exc.details.get("error_type"),
                        }
                    },
                )
                raise

            _EXTRACTED_DOCUMENT_STORE[doc_id] = extracted
            extracted_docs.append(extracted)

        if not extracted_docs:
            raise ValueError("No matching file bytes found for ingestion files")

        logger.info(
            "ingestion_extraction_completed",
            extra={
                "context": {
                    "ingestion_id": str(ingestion.ingestion_id),
                    "document_id": str(ingestion.document_id),
                    "file_count": len(ingestion.files),
                    "extracted_documents": len(extracted_docs),
                }
            },
        )

        return extracted_docs


def get_extracted_document(document_id: UUID) -> Optional[ExtractedDocument]:
    """Return the extracted document for the given document_id, if present."""

    return _EXTRACTED_DOCUMENT_STORE.get(document_id)
