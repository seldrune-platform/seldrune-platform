import pymupdf
import pytest

from backend.app.services.pdf_creator import PDFCreationError, create_text_pdf


def test_create_text_pdf_keeps_markdown_structure_and_unicode():
    result = create_text_pdf(
        "Plant care guide",
        "# Plant care guide\n\n**Water:** lightly.\n\n"
        "- Give bright indirect light\n- Let soil dry between watering\n\nவணக்கம் 🌱",
    )

    document = pymupdf.open(stream=result.data, filetype="pdf")
    rendered_text = "\n".join(page.get_text() for page in document)
    assert result.data.startswith(b"%PDF-")
    assert result.page_count == document.page_count == 1
    assert "Plant care guide" in rendered_text
    assert "Give bright indirect light" in rendered_text
    assert "வணக்கம்" in rendered_text


def test_create_text_pdf_paginates_long_documents():
    content = "\n\n".join(
        f"## Section {index}\n\n" + "Seldrune creates readable deliverables. " * 40
        for index in range(30)
    )

    result = create_text_pdf("Long report", content)
    document = pymupdf.open(stream=result.data, filetype="pdf")
    assert result.page_count == document.page_count
    assert result.page_count > 1


@pytest.mark.parametrize(
    ("title", "content", "message"),
    [
        ("", "content", "title"),
        ("Title", "", "document text"),
        ("Title", "x" * 100_001, "limited to"),
    ],
)
def test_create_text_pdf_rejects_invalid_input(title, content, message):
    with pytest.raises(PDFCreationError, match=message):
        create_text_pdf(title, content)
