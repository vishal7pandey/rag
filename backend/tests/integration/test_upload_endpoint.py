from pathlib import Path

from backend.api.schemas import IngestionResponse


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _ensure_sample_file(name: str, content: bytes) -> Path:
    path = FIXTURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return path


def test_upload_single_text_file(client) -> None:
    """Uploading a small text file returns 202 and a valid IngestionResponse."""

    sample_path = _ensure_sample_file("sample_upload.txt", b"hello world")

    with sample_path.open("rb") as f:
        files = {"files": ("sample_upload.txt", f, "text/plain")}
        response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 202
    data = response.json()
    model = IngestionResponse(**data)

    assert model.status.value == "pending"
    assert model.chunks_created == 0
    assert model.progress_percent == 0


def test_upload_no_files_returns_validation_error(client) -> None:
    """Uploading with no files returns a FileValidationError envelope (400)."""

    response = client.post("/api/ingest/upload", files=[])

    assert response.status_code == 400
    body = response.json()

    assert "error" in body
    assert body["error"]["type"] == "FileValidationError"
    assert "No files provided" in body["error"]["message"]


def test_upload_unsupported_format_returns_400(client) -> None:
    """Uploading an unsupported file type (.exe) returns a validation error."""

    files = {"files": ("script.exe", b"MZ\x90\x00", "application/x-msdownload")}
    response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 400
    body = response.json()

    assert body["error"]["type"] == "FileValidationError"
    errors = body["error"]["details"].get("validation_errors", [])
    assert any("Unsupported file type" in e.get("error", "") for e in errors)


def test_upload_file_too_large_returns_400(client) -> None:
    """Uploading a file larger than 50MB returns a validation error."""

    large_content = b"x" * (60 * 1024 * 1024)  # 60MB
    files = {"files": ("large.pdf", large_content, "application/pdf")}
    response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 400
    body = response.json()

    assert body["error"]["type"] == "FileValidationError"
    errors = body["error"]["details"].get("validation_errors", [])
    assert any("exceeds 50 MB limit" in e.get("error", "") for e in errors)


def test_upload_returns_trace_id_header(client) -> None:
    """Responses from /api/ingest/upload include X-Trace-ID from LoggingMiddleware."""

    sample_path = _ensure_sample_file("sample_upload_trace.txt", b"hello world")

    with sample_path.open("rb") as f:
        files = {"files": ("sample_upload_trace.txt", f, "text/plain")}
        response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 202
    assert "X-Trace-ID" in response.headers
    assert response.headers["X-Trace-ID"]


def test_upload_multiple_files_success(client) -> None:
    """Uploading multiple files in a single request succeeds and returns file metadata."""

    files = [
        ("files", ("doc1.txt", b"one", "text/plain")),
        ("files", ("doc2.txt", b"two", "text/plain")),
        ("files", ("doc3.txt", b"three", "text/plain")),
    ]

    response = client.post("/api/ingest/upload", files=files)
    assert response.status_code == 202

    data = response.json()
    model = IngestionResponse(**data)

    filenames = {f.filename for f in model.files}
    assert {"doc1.txt", "doc2.txt", "doc3.txt"} <= filenames


def test_upload_rate_limited_returns_429(client) -> None:
    """Exceeding the upload rate limit returns 429 with Retry-After header."""

    files = {"files": ("rl.txt", b"data", "text/plain")}
    headers = {"X-User-ID": "rate-limit-user"}

    # Hit the endpoint up to the configured limit (100) for this user.
    for _ in range(100):
        resp = client.post("/api/ingest/upload", files=files, headers=headers)
        assert resp.status_code in {
            202,
            400,
        }  # 400 possible from validation, but should not 429 yet

    # Next request should trigger rate limiting.
    response = client.post("/api/ingest/upload", files=files, headers=headers)

    assert response.status_code == 429
    body = response.json()

    assert body["error"]["type"] == "RateLimitError"
    assert body["error"]["status_code"] == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) >= 0
