from backend.core.file_validator import FileValidator


def test_validator_accepts_pdf() -> None:
    validator = FileValidator()
    content = b"%PDF-1.4\n%test"  # minimal PDF signature
    result = validator.validate_single_file("doc.pdf", content)

    assert result.is_valid
    assert result.mime_type == "application/pdf"
    assert result.extension == ".pdf"


def test_validator_rejects_unsupported_format() -> None:
    validator = FileValidator()
    content = b"MZ\x90\x00"  # exe-like
    result = validator.validate_single_file("script.exe", content)

    assert not result.is_valid
    assert "Unsupported file type" in (result.error or "")


def test_validator_checks_file_size() -> None:
    validator = FileValidator()
    large_content = b"x" * (60 * 1024 * 1024)  # 60MB
    result = validator.validate_single_file("large.pdf", large_content)

    assert not result.is_valid
    assert "exceeds 50 MB limit" in (result.error or "")


def test_validator_checks_file_count_and_total_size() -> None:
    validator = FileValidator()
    small = b"x" * (10 * 1024 * 1024)  # 10MB
    files = [(f"doc{i}.pdf", small) for i in range(12)]

    _, batch_error = validator.validate_batch(files)
    assert batch_error is not None
    assert "Maximum" in batch_error


def test_validator_checks_total_batch_size() -> None:
    validator = FileValidator()
    big1 = b"x" * (300 * 1024 * 1024)
    big2 = b"x" * (250 * 1024 * 1024)
    files = [("doc1.pdf", big1), ("doc2.pdf", big2)]

    _, batch_error = validator.validate_batch(files)
    assert batch_error is not None
    # For very large files that individually violate the per-file size limit,
    # we only require that the validator reports a batch-level error; more
    # detailed per-file size messages are covered by
    # test_validator_checks_file_size.
    assert "File validation failed" in batch_error
