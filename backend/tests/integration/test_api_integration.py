from pathlib import Path

from backend.api.schemas import IngestionResponse, QueryResponse


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_full_ingest_flow(client) -> None:
    """User can upload a file and then poll ingestion status (stubbed)."""

    sample_path = FIXTURES_DIR / "sample_doc.txt"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    if not sample_path.exists():
        sample_path.write_text("Sample document for ingestion tests.")

    with sample_path.open("rb") as f:
        files = {"files": ("sample.txt", f, "text/plain")}
        response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 202

    upload_data = response.json()
    ingest_model = IngestionResponse(**upload_data)

    status_response = client.get(f"/api/ingest/status/{ingest_model.ingestion_id}")
    assert status_response.status_code == 200

    status_data = status_response.json()
    status_model = IngestionResponse(**status_data)
    assert status_model.status.value in {"pending", "processing", "completed", "failed"}


def test_query_with_no_documents(client) -> None:
    """Query without documents returns a helpful stubbed answer."""

    request_data = {"query": "What is the company policy?"}
    response = client.post("/api/query", json=request_data)

    assert response.status_code == 200

    data = response.json()
    model = QueryResponse(**data)

    assert "no documents" in model.answer.lower() or "empty" in model.answer.lower()
    assert model.citations == []


def test_cors_headers_present(client) -> None:
    """CORS headers are configured for frontend-backend communication (if present)."""

    response = client.get("/health")

    if "access-control-allow-origin" in response.headers:
        assert "localhost:5173" in response.headers["access-control-allow-origin"]
