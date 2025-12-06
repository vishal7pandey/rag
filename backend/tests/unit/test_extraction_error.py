import pytest

from backend.core.exceptions import ExtractionError
from backend.core.format_detector import FormatDetector


def test_format_detector_raises_extraction_error_for_unsupported_format() -> None:
    detector = FormatDetector()

    with pytest.raises(ExtractionError) as exc_info:
        detector.detect_format("script.exe", b"MZ\x90")

    err = exc_info.value
    assert err.details.get("error_type") == "unsupported_format"
    assert err.details.get("filename") == "script.exe"
