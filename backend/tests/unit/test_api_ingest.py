import json

from backend.api.schemas import IngestionResponse, IngestionStatus


def test_ingest_upload_requires_files(client) -> None:
    """POST /api/ingest/upload without files should return 400."""

    response = client.post("/api/ingest/upload", files=[])
    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert body["error"]["type"] == "FileValidationError"
    assert "No files provided" in body["error"]["message"]


def test_ingest_upload_accepts_file(client, tmp_path) -> None:
    """POST /api/ingest/upload with a small text file returns 202 and ingestion_id."""

    sample_path = tmp_path / "sample.txt"
    sample_path.write_text("hello world")

    with sample_path.open("rb") as f:
        files = {"files": ("sample.txt", f, "text/plain")}
        response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 202

    data = response.json()
    model = IngestionResponse(**data)

    assert model.status == IngestionStatus.PENDING
    assert model.chunks_created == 0
    assert model.progress_percent == 0


def test_ingest_upload_with_metadata_and_config(client, tmp_path) -> None:
    """Metadata and config fields are accepted and validated when present."""

    sample_path = tmp_path / "sample.txt"
    sample_path.write_text("hello world")

    metadata = {"category": "technical", "language": "en", "source": "unit-test"}
    config = {"chunk_size_tokens": 256, "chunk_overlap_tokens": 32}

    with sample_path.open("rb") as f:
        files = {"files": ("sample.txt", f, "text/plain")}
        data = {
            "document_metadata": json.dumps(metadata),
            "ingestion_config": json.dumps(config),
        }
        response = client.post("/api/ingest/upload", files=files, data=data)

    assert response.status_code == 202


def test_ingest_status_not_found(client) -> None:
    """GET /api/ingest/status for unknown id returns 404."""

    # Use a random UUID that is extremely unlikely to exist
    unknown_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/ingest/status/{unknown_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ingestion not found"
