from uuid import uuid4

import pytest

from backend.core.data_models import ExtractedDocument
from backend.core.text_extraction_service import TextExtractionService


def test_text_extraction_flow_txt() -> None:
    """End-to-end extraction for a plain text document."""

    service = TextExtractionService()
    content = "Hello World\nLine 2\nLine 3".encode("utf-8")

    result = service.extract(
        filename="sample.txt",
        content=content,
        document_id=uuid4(),
    )

    assert isinstance(result, ExtractedDocument)
    assert result.format == "txt"
    assert result.total_pages >= 1
    assert any("Hello World" in page.raw_text for page in result.pages)
    assert result.language == "en"


def test_text_extraction_flow_markdown() -> None:
    """End-to-end extraction for a markdown document with headings and frontmatter."""

    service = TextExtractionService()
    md_content = """---
    title: My Document
    ---
    # Main Title

    Content for main.

    ## Subsection

    Content for sub.""".encode("utf-8")

    result = service.extract(
        filename="doc.md",
        content=md_content,
        document_id=uuid4(),
    )

    assert isinstance(result, ExtractedDocument)
    assert result.format == "markdown"
    assert result.total_pages == 1
    assert (
        result.pages[0].section_title in {"Main Title", "Subsection"}
        or result.pages[0].section_title is not None
    )
    # Either frontmatter or heading should be reflected somewhere.
    assert (
        "title" in result.extraction_metadata
        or "Main Title" in result.pages[0].raw_text
    )


@pytest.mark.skip(
    "PDF end-to-end extraction flow will be enabled once pdfplumber and fixtures are configured."
)
def test_text_extraction_flow_pdf() -> None:
    """Placeholder for PDF extraction flow using TextExtractionService."""

    assert True
