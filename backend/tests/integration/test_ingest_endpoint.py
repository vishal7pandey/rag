from __future__ import annotations

from uuid import uuid4

from backend.api.schemas import IngestionResponse


def test_ingest_endpoint_returns_202_and_runs_pipeline(client) -> None:
    """POST /ingest returns 202 and a valid IngestionResponse with progress."""

    files = {"files": ("doc.txt", b"hello world", "text/plain")}

    response = client.post("/ingest", files=files)

    assert response.status_code == 202
    data = response.json()
    model = IngestionResponse(**data)

    assert model.ingestion_id
    assert model.document_id is not None
    # Orchestration is synchronous in this story, so we expect COMPLETED.
    assert model.status.value in {"completed", "failed"}
    assert 0 <= model.progress_percent <= 100
    assert model.chunks_created >= 0


def test_ingest_status_endpoint_returns_job_state(client) -> None:
    """GET /ingest/status/{id} returns current job state created by /ingest."""

    files = {"files": ("status-doc.txt", b"hello world", "text/plain")}

    upload_resp = client.post("/ingest", files=files)
    assert upload_resp.status_code == 202
    upload_data = upload_resp.json()
    ingestion_id = upload_data["ingestion_id"]

    status_resp = client.get(f"/ingest/status/{ingestion_id}")
    assert status_resp.status_code == 200

    data = status_resp.json()
    model = IngestionResponse(**data)

    assert str(model.ingestion_id) == ingestion_id
    assert model.status.value in {"pending", "processing", "completed", "failed"}


def test_ingest_status_not_found_returns_404(client) -> None:
    """GET /ingest/status with unknown ID returns 404."""

    unknown_id = uuid4()

    response = client.get(f"/ingest/status/{unknown_id}")

    assert response.status_code == 404


def test_ingest_inherits_validation_from_upload(client) -> None:
    """/ingest enforces the same file validation rules as /api/ingest/upload."""

    # No files
    response = client.post("/ingest")
    assert response.status_code == 400

    # Unsupported format
    files = {"files": ("bad.exe", b"MZ\x90\x00", "application/x-msdownload")}
    response = client.post("/ingest", files=files)
    assert response.status_code == 400
