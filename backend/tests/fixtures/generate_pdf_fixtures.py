"""Generate PDF test fixtures for PDF extraction tests.

Run this script once to create the fixture files:
    python -m backend.tests.fixtures.generate_pdf_fixtures

The generated PDFs are committed to the repo so tests don't require reportlab.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FIXTURES_DIR = Path(__file__).parent


def create_single_page_pdf() -> None:
    """Create a simple single-page PDF with searchable text."""
    filepath = FIXTURES_DIR / "sample_single_page.pdf"
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(72, height - 72, "Sample Document")

    # Body text
    c.setFont("Helvetica", 12)
    y = height - 120
    lines = [
        "This is a sample PDF document for testing text extraction.",
        "It contains multiple lines of searchable text that can be extracted",
        "using pdfplumber or similar PDF parsing libraries.",
        "",
        "The document includes:",
        "- Plain text content",
        "- Multiple paragraphs",
        "- Basic formatting",
        "",
        "This text should be fully extractable and normalized by the",
        "PDF extraction pipeline. The extraction should preserve the",
        "logical reading order and produce clean, usable text output.",
    ]
    for line in lines:
        c.drawString(72, y, line)
        y -= 18

    c.save()
    print(f"Created: {filepath}")


def create_multi_page_pdf() -> None:
    """Create a multi-page PDF with different content on each page."""
    filepath = FIXTURES_DIR / "sample_multi_page.pdf"
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    for page_num in range(1, 6):
        # Page header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(72, height - 72, f"Page {page_num} of 5")

        # Page content
        c.setFont("Helvetica", 12)
        y = height - 120

        content = [
            f"This is the content of page {page_num}.",
            "",
            "Each page contains unique text to verify that page-by-page",
            "extraction works correctly. The extractor should identify",
            f"this as page number {page_num - 1} (0-indexed).",
            "",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco.",
            "",
            f"End of page {page_num} content.",
        ]

        for line in content:
            c.drawString(72, y, line)
            y -= 18

        # Page footer
        c.setFont("Helvetica", 10)
        c.drawString(72, 36, f"Footer - Page {page_num}")

        if page_num < 5:
            c.showPage()

    c.save()
    print(f"Created: {filepath}")


def create_empty_pages_pdf() -> None:
    """Create a PDF with some empty/near-empty pages."""
    filepath = FIXTURES_DIR / "sample_with_empty_pages.pdf"
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    # Page 1: Normal content
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Page 1 - With Content")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 100, "This page has substantial text content.")
    c.drawString(72, height - 118, "It should be marked as non-empty by the extractor.")
    c.drawString(
        72, height - 136, "The word count and character count should be positive."
    )
    c.showPage()

    # Page 2: Completely empty (no text at all)
    c.showPage()

    # Page 3: Nearly empty (just whitespace or minimal text)
    c.setFont("Helvetica", 8)
    c.drawString(72, height - 72, " ")  # Just a space
    c.showPage()

    # Page 4: Normal content again
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Page 4 - With Content")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 100, "This page also has text content.")
    c.drawString(72, height - 118, "It follows two empty or near-empty pages.")

    c.save()
    print(f"Created: {filepath}")


def create_pdf_with_tables() -> None:
    """Create a PDF containing tables for table detection testing."""
    filepath = FIXTURES_DIR / "sample_with_tables.pdf"
    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        spaceAfter=30,
    )
    story.append(Paragraph("Document with Tables", title_style))
    story.append(Spacer(1, 12))

    # Intro text
    story.append(
        Paragraph(
            "This document contains tables to test table detection capabilities. "
            "The PDF extractor should identify pages containing tables and mark them "
            "appropriately in the extraction metadata.",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 24))

    # Table 1: Simple data table
    story.append(Paragraph("Table 1: Product Inventory", styles["Heading2"]))
    story.append(Spacer(1, 12))

    table_data = [
        ["Product ID", "Name", "Quantity", "Price"],
        ["P001", "Widget A", "150", "$10.00"],
        ["P002", "Widget B", "75", "$15.50"],
        ["P003", "Gadget X", "200", "$25.00"],
        ["P004", "Gadget Y", "50", "$30.00"],
    ]

    table = Table(table_data, colWidths=[1.2 * inch, 1.5 * inch, 1 * inch, 1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 24))

    # More text
    story.append(
        Paragraph(
            "The table above shows inventory data. Below is another table with "
            "different structure to test varied table formats.",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 24))

    # Table 2: Different structure
    story.append(Paragraph("Table 2: Quarterly Results", styles["Heading2"]))
    story.append(Spacer(1, 12))

    table_data_2 = [
        ["Quarter", "Revenue", "Expenses", "Profit"],
        ["Q1 2024", "$1,200,000", "$800,000", "$400,000"],
        ["Q2 2024", "$1,350,000", "$850,000", "$500,000"],
        ["Q3 2024", "$1,100,000", "$750,000", "$350,000"],
        ["Q4 2024", "$1,500,000", "$900,000", "$600,000"],
        ["Total", "$5,150,000", "$3,300,000", "$1,850,000"],
    ]

    table2 = Table(
        table_data_2, colWidths=[1 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch]
    )
    table2.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    story.append(table2)

    doc.build(story)
    print(f"Created: {filepath}")


def create_large_text_pdf() -> None:
    """Create a PDF with substantial text for chunking tests."""
    filepath = FIXTURES_DIR / "sample_large_text.pdf"
    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(
        Paragraph("Comprehensive RAG System Documentation", styles["Heading1"])
    )
    story.append(Spacer(1, 12))

    sections = [
        (
            "Introduction to RAG",
            """
        Retrieval-Augmented Generation (RAG) is a technique that enhances large language 
        models by providing them with relevant context retrieved from a knowledge base. 
        This approach combines the strengths of retrieval-based and generation-based methods 
        to produce more accurate and contextually relevant responses.
        
        The RAG pipeline typically consists of several stages: document ingestion, text 
        extraction, chunking, embedding generation, vector storage, retrieval, and finally 
        response generation. Each stage plays a crucial role in the overall system performance.
        """,
        ),
        (
            "Document Ingestion",
            """
        Document ingestion is the first stage of the RAG pipeline. It involves accepting 
        various document formats (PDF, TXT, MD, etc.) and preparing them for processing. 
        The ingestion system must handle file validation, format detection, and error 
        handling for corrupted or unsupported files.
        
        Key considerations for document ingestion include:
        - File size limits and validation
        - Format detection and routing to appropriate extractors
        - Metadata extraction and preservation
        - Error handling and user feedback
        - Batch processing for multiple files
        """,
        ),
        (
            "Text Extraction",
            """
        Text extraction converts raw document bytes into structured text that can be 
        processed by downstream components. Different document formats require different 
        extraction strategies. PDF extraction is particularly challenging due to the 
        variety of PDF types (searchable, scanned, mixed) and complex layouts.
        
        The extraction pipeline should:
        - Preserve document structure where possible
        - Handle multi-column layouts correctly
        - Extract tables and preserve their structure
        - Detect and handle empty or near-empty pages
        - Provide confidence scores for extraction quality
        """,
        ),
        (
            "Chunking Strategies",
            """
        Chunking divides extracted text into smaller segments suitable for embedding and 
        retrieval. The chunking strategy significantly impacts retrieval quality. Common 
        approaches include fixed-size chunking, semantic chunking, and structure-aware 
        chunking that respects document boundaries.
        
        Important chunking parameters:
        - Chunk size (typically 512-2048 tokens)
        - Overlap between chunks (typically 10-20%)
        - Boundary detection (sentences, paragraphs, sections)
        - Metadata preservation per chunk
        """,
        ),
        (
            "Embedding and Vector Storage",
            """
        Embeddings are dense vector representations of text chunks that capture semantic 
        meaning. These vectors are stored in a vector database that supports efficient 
        similarity search. Popular embedding models include OpenAI's text-embedding-3-small 
        and various open-source alternatives.
        
        Vector storage considerations:
        - Embedding dimension (typically 384-1536)
        - Index type (HNSW, IVF, etc.)
        - Distance metric (cosine, euclidean, dot product)
        - Scalability and query performance
        """,
        ),
    ]

    for title, content in sections:
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(Spacer(1, 6))
        for para in content.strip().split("\n\n"):
            story.append(Paragraph(para.strip(), styles["Normal"]))
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 12))

    doc.build(story)
    print(f"Created: {filepath}")


def create_encrypted_pdf() -> None:
    """Create a password-protected PDF for encryption handling tests."""
    filepath = FIXTURES_DIR / "sample_encrypted.pdf"
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Encrypted Document")

    c.setFont("Helvetica", 12)
    c.drawString(72, height - 100, "This document is password protected.")
    c.drawString(72, height - 118, "The password is: testpassword")

    # Note: reportlab's canvas.encrypt() method can add encryption
    # For testing, we'll create an unencrypted version and note that
    # real encrypted PDFs would need PyPDF2 or similar to create
    c.save()

    # Now encrypt it using PyPDF2 if available
    try:
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(str(filepath))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(user_password="testpassword", owner_password="ownerpass")

        with open(filepath, "wb") as f:
            writer.write(f)

        print(f"Created (encrypted): {filepath}")
    except ImportError:
        print(f"Created (unencrypted - PyPDF2 not available): {filepath}")


def create_minimal_pdf() -> None:
    """Create a minimal valid PDF for edge case testing."""
    filepath = FIXTURES_DIR / "sample_minimal.pdf"
    c = canvas.Canvas(str(filepath), pagesize=letter)
    # Single character to make it technically non-empty but minimal
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "X")
    c.save()
    print(f"Created: {filepath}")


def main() -> None:
    """Generate all PDF fixtures."""
    print("Generating PDF test fixtures...")
    print(f"Output directory: {FIXTURES_DIR}")
    print()

    create_single_page_pdf()
    create_multi_page_pdf()
    create_empty_pages_pdf()
    create_pdf_with_tables()
    create_large_text_pdf()
    create_encrypted_pdf()
    create_minimal_pdf()

    print()
    print("Done! All fixtures created.")


if __name__ == "__main__":
    main()
