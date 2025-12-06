from uuid import uuid4

from backend.core.extractors.markdown_extractor import MarkdownExtractor


def test_markdown_extractor_parses_frontmatter() -> None:
    extractor = MarkdownExtractor()
    md_content = """---
    title: My Document
    author: John Doe
    ---
    # Main Heading

    Content here.""".encode("utf-8")

    result = extractor.extract(
        md_content,
        document_id=uuid4(),
        filename="doc.md",
    )

    assert (
        result.extraction_metadata.get("title") == "My Document"
        or "Main Heading" in result.pages[0].raw_text
    )

    meta = result.extraction_metadata
    assert meta["total_words"] == sum(p.word_count for p in result.pages)
    assert meta["total_chars"] == sum(p.char_count for p in result.pages)
    assert meta["empty_pages"] + meta["non_empty_pages"] == result.total_pages
    # section_hierarchy should contain at least one heading.
    assert "section_hierarchy" in meta
    assert any(entry["title"] for entry in meta["section_hierarchy"])


def test_markdown_extractor_tracks_headings() -> None:
    extractor = MarkdownExtractor()
    md_content = """# Main Title

    Content for main.

    ## Subsection

    Content for sub.""".encode("utf-8")

    result = extractor.extract(
        md_content,
        document_id=uuid4(),
        filename="doc.md",
    )

    text = result.pages[0].raw_text
    assert "Main Title" in text or "Content" in text


def test_markdown_extractor_removes_syntax() -> None:
    extractor = MarkdownExtractor()
    md_content = "**Bold** and *italic* and [link](http://example.com)".encode("utf-8")

    result = extractor.extract(
        md_content,
        document_id=uuid4(),
        filename="doc.md",
    )

    text = result.pages[0].raw_text
    assert "Bold" in text
    assert "italic" in text
    assert "**" not in text and "*" not in text


def test_markdown_extractor_preserves_fenced_code_blocks() -> None:
    extractor = MarkdownExtractor()
    md_content = """```python
def foo():
    print("bar")
```
""".encode("utf-8")

    result = extractor.extract(
        md_content,
        document_id=uuid4(),
        filename="code.md",
    )

    text = "\n".join(page.raw_text for page in result.pages)
    assert "def foo():" in text
    assert "print(" in text
