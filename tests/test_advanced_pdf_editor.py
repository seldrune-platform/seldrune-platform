import pymupdf
import pytest

from backend.app.services.pdf_editor import (
    PDFEditorError,
    apply_pdf_edit_plan,
    inspect_pdf,
    prepare_pdf_for_model,
)


def _text_pdf(text: str = "Invoice date: 2025-09-23") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    output = document.tobytes()
    document.close()
    return output


def test_inspection_classifies_native_text_pdf() -> None:
    inspection = inspect_pdf(_text_pdf())
    assert inspection.page_count == 1
    assert inspection.native_text_pages == 1
    assert inspection.image_only_pages == 0
    assert inspection.document_type == "native_text"


def test_native_replace_preserves_integrity_and_verifies() -> None:
    result = apply_pdf_edit_plan(
        _text_pdf(),
        {
            "summary": "Update invoice date",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "2025-09-23",
                    "replacement_text": "2026-09-23",
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                }
            ],
        },
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    text = output[0].get_text()
    assert output.page_count == 1
    output.close()

    assert "2026-09-23" in text
    assert "2025-09-23" not in text
    assert result.applied_edits == 1
    assert result.verified_operations == 1
    assert result.verification_score == 100


def test_visual_bbox_replacement_handles_image_only_style_page() -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.draw_rect(
        pymupdf.Rect(40, 40, 360, 260),
        color=(0.8, 0.8, 0.8),
        fill=(0.96, 0.96, 0.96),
    )
    source = document.tobytes()
    document.close()

    inspection = inspect_pdf(source)
    assert inspection.document_type == "scanned_or_image"

    result = apply_pdf_edit_plan(
        source,
        {
            "summary": "Replace visual region",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "unsearchable scanned value",
                    "replacement_text": "Corrected value",
                    "text": None,
                    "bbox": [180, 300, 820, 430],
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                }
            ],
        },
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    assert "Corrected value" in output[0].get_text()
    output.close()
    assert result.applied_edits == 1
    assert any("visual-region edit" in note for note in result.verification_notes)


def test_form_field_edit_updates_interactive_form() -> None:
    document = pymupdf.open()
    page = document.new_page()
    widget = pymupdf.Widget()
    widget.field_name = "Customer Name"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 72, 240, 100)
    page.add_widget(widget)
    source = document.tobytes()
    document.close()

    inspection = inspect_pdf(source)
    assert inspection.form_fields == 1
    assert inspection.document_type == "interactive_form"

    result = apply_pdf_edit_plan(
        source,
        {
            "summary": "Fill customer name",
            "operations": [
                {
                    "action": "fill_form",
                    "page": 1,
                    "target_text": None,
                    "replacement_text": None,
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": "customer name",
                    "value": "Seldrune Labs",
                    "degrees": None,
                    "font_size": None,
                }
            ],
        },
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    output_page = output[0]
    output_widget = list(output_page.widgets() or [])[0]
    assert output_widget.field_value == "Seldrune Labs"
    output.close()
    assert result.verification_score == 100


def test_password_protected_pdf_can_be_prepared_and_edited() -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Protected value: OLD")
    protected = document.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="reader-password",
    )
    document.close()

    with pytest.raises(PDFEditorError):
        inspect_pdf(protected)

    prepared = prepare_pdf_for_model(protected, "reader-password")
    prepared_document = pymupdf.open(stream=prepared, filetype="pdf")
    assert not prepared_document.needs_pass
    assert "Protected value: OLD" in prepared_document[0].get_text()
    prepared_document.close()

    result = apply_pdf_edit_plan(
        protected,
        {
            "summary": "Edit protected PDF",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "OLD",
                    "replacement_text": "NEW",
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                }
            ],
        },
        password="reader-password",
    )
    edited = pymupdf.open(stream=result.data, filetype="pdf")
    assert "NEW" in edited[0].get_text()
    edited.close()


def test_rotation_operation_is_verified() -> None:
    result = apply_pdf_edit_plan(
        _text_pdf("Rotate me"),
        {
            "summary": "Rotate page",
            "operations": [
                {
                    "action": "rotate_page",
                    "page": 1,
                    "target_text": None,
                    "replacement_text": None,
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": 90,
                    "font_size": None,
                }
            ],
        },
    )
    output = pymupdf.open(stream=result.data, filetype="pdf")
    assert output[0].rotation == 90
    output.close()
    assert result.verification_score == 100


def test_native_replace_reconstructs_original_font_size_color_and_baseline() -> None:
    document = pymupdf.open()
    page = document.new_page(width=500, height=300)
    page.draw_rect(
        pymupdf.Rect(40, 55, 460, 115),
        color=(0.15, 0.35, 0.55),
        fill=(0.93, 0.95, 0.98),
        width=1.5,
    )
    page.insert_text(
        pymupdf.Point(92, 92),
        "Original total: OLD",
        fontname="tibo",
        fontsize=18,
        color=(0.2, 0.35, 0.55),
    )
    source = document.tobytes()
    original_drawings = len(page.get_drawings())
    document.close()

    result = apply_pdf_edit_plan(
        source,
        {
            "summary": "Replace total while preserving appearance",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "OLD",
                    "replacement_text": "NEW",
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                }
            ],
        },
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    output_page = output[0]
    spans = [
        span
        for block in output_page.get_text("dict").get("blocks", [])
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if "NEW" in str(span.get("text") or "")
    ]
    assert spans
    replacement = spans[0]

    assert "times" in str(replacement["font"]).casefold()
    assert "bold" in str(replacement["font"]).casefold()
    assert float(replacement["size"]) == pytest.approx(18.0, abs=0.2)
    assert int(replacement["color"]) == 0x33598C
    assert float(replacement["origin"][1]) == pytest.approx(92.0, abs=0.8)
    assert len(output_page.get_drawings()) == original_drawings
    output.close()

    assert any(
        "original-look reconstruction" in note
        for note in result.verification_notes
    )
    assert result.visual_fidelity_score == 100


def test_native_replace_keeps_original_point_size_for_longer_text() -> None:
    document = pymupdf.open()
    page = document.new_page(width=500, height=300)
    page.insert_text(
        pymupdf.Point(72, 90),
        "Code OLD",
        fontname="hebo",
        fontsize=15,
        color=(0.0, 0.0, 0.0),
    )
    source = document.tobytes()
    document.close()

    result = apply_pdf_edit_plan(
        source,
        {
            "summary": "Replace code",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "OLD",
                    "replacement_text": "LONGER",
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                }
            ],
        },
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    spans = [
        span
        for block in output[0].get_text("dict").get("blocks", [])
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if "LONGER" in str(span.get("text") or "")
    ]
    assert spans
    assert float(spans[0]["size"]) == pytest.approx(15.0, abs=0.2)
    assert "bold" in str(spans[0]["font"]).casefold()
    output.close()


def test_visual_bbox_uses_ai_inferred_typography() -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.draw_rect(
        pymupdf.Rect(40, 80, 360, 150),
        color=None,
        fill=(0.94, 0.94, 0.94),
    )
    source = document.tobytes()
    document.close()

    result = apply_pdf_edit_plan(
        source,
        {
            "summary": "Reconstruct scanned label",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "scanned source",
                    "replacement_text": "Styled replacement",
                    "text": None,
                    "bbox": [100, 300, 900, 500],
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": 16,
                    "font_family_hint": "Times",
                    "font_weight": "bold",
                    "font_style": "regular",
                    "alignment": "center",
                    "text_color": [0.8, 0.1, 0.1],
                    "background_color": [0.94, 0.94, 0.94],
                }
            ],
        },
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    spans = [
        span
        for block in output[0].get_text("dict").get("blocks", [])
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if "Styled replacement" in str(span.get("text") or "")
    ]
    assert spans
    span = spans[0]
    assert "times" in str(span["font"]).casefold()
    assert "bold" in str(span["font"]).casefold()
    assert float(span["size"]) == pytest.approx(16.0, abs=0.4)
    assert int(span["color"]) == 0xCC1A1A
    output.close()

    assert result.visual_fidelity_score is None
