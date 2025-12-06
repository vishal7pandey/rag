from uuid import UUID

from backend.api.schemas import IngestionResponse


def test_full_upload_and_status_flow(client) -> None:
    """End-to-end flow: upload file, then poll /api/ingest/status.

    This uses the validation-aware upload endpoint and the enriched
    IngestionResponse schema (including document_id and files).
    """

    # Step 1: upload a small text file
    sample_content = b"hello for full flow"
    files = {"files": ("flow.txt", sample_content, "text/plain")}

    upload_response = client.post("/api/ingest/upload", files=files)
    assert upload_response.status_code == 202

    upload_data = upload_response.json()
    upload_model = IngestionResponse(**upload_data)

    assert isinstance(upload_model.ingestion_id, UUID)
    assert upload_model.status.value == "pending"
    assert upload_model.document_id is not None
    # We should see at least one file entry with the uploaded name.
    assert any(f.filename == "flow.txt" for f in upload_model.files)

    # Step 2: poll status using the returned ingestion_id
    status_response = client.get(f"/api/ingest/status/{upload_model.ingestion_id}")
    assert status_response.status_code == 200

    status_data = status_response.json()
    status_model = IngestionResponse(**status_data)

    assert status_model.ingestion_id == upload_model.ingestion_id
    assert status_model.status.value in {"pending", "processing", "completed", "failed"}
    # Status response should include the same file metadata and document_id.
    assert status_model.document_id == upload_model.document_id
    assert any(f.filename == "flow.txt" for f in status_model.files)
