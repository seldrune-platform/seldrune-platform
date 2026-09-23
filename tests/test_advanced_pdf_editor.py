import pymupdf
import pytest

from backend.app.services.pdf_editor import (
    PDFEditorError,
    PDFTextStyle,
    _replacement_visual_fidelity,
    apply_pdf_edit_plan,
    assess_pdf_edit_candidate,
    inspect_pdf,
    validate_pdf_edit_plan,
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


def _salary_offer_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((210, 92), "ANNEXURE - I", fontname="hebo", fontsize=12)
    page.insert_text((190, 112), "SALARY OFFER SHEET", fontname="hebo", fontsize=12)
    page.insert_text((50, 148), "Name: Giridharan V", fontsize=10)
    page.insert_text((50, 164), "Location: Chennai", fontsize=10)
    page.insert_text((50, 180), "Position: Assistant Manager", fontsize=10)
    page.insert_text((50, 196), "Band: B2", fontsize=10)
    page.insert_text((50, 212), "Career Stream: FUNCTION STREAM", fontsize=10)
    page.insert_text((50, 228), "Rs. 1253181.00", fontsize=10)
    page.insert_text(
        (50, 252),
        "Your compensation is as detailed below, subject to withholding taxes.",
        fontsize=10,
    )

    left = 50
    divider = 450
    right = 562
    top = 270
    row_height = 24
    rows = 6
    page.draw_rect(
        pymupdf.Rect(left, top, right, top + row_height * rows),
        color=(0, 0, 0),
        width=0.8,
    )
    page.draw_line(
        pymupdf.Point(divider, top),
        pymupdf.Point(divider, top + row_height * rows),
        color=(0, 0, 0),
        width=0.8,
    )
    for index in range(1, rows):
        y = top + row_height * index
        page.draw_line(
            pymupdf.Point(left, y),
            pymupdf.Point(right, y),
            color=(0, 0, 0),
            width=0.8,
        )

    page.insert_text((200, 287), "Components", fontname="hebo", fontsize=10)
    page.insert_text((52, 311), "BASIC SALARY", fontsize=10)
    page.insert_text((490, 311), "2105000.00", fontsize=10)
    page.insert_text((52, 335), "HOUSE RENT ALLOWANCE", fontsize=10)
    page.insert_text((490, 335), "0", fontsize=10)
    page.insert_text((52, 359), "BONUS (estimated but paid as per Company policy)", fontsize=10)
    page.insert_text((490, 359), "450000.00", fontsize=10)
    page.insert_text((52, 383), "WIPRO BENEFITS PLAN as per Company policy", fontsize=10)
    page.insert_text((490, 383), "0", fontsize=10)

    output = document.tobytes()
    document.close()
    return output


def test_salary_table_multi_edit_keeps_values_in_original_rows_without_overlap() -> None:
    source = _salary_offer_pdf()
    plan = {
        "summary": "Update compensation figures",
        "operations": [
            {
                "action": "replace_text",
                "page": 1,
                "target_text": "1253181.00",
                "replacement_text": "2306900.00",
                "text": None,
                "bbox": None,
                "occurrence": None,
                "field_name": None,
                "value": None,
                "degrees": None,
                "font_size": None,
            },
            {
                "action": "replace_text",
                "page": 1,
                "target_text": "2105000.00",
                "replacement_text": "2150000.00",
                "text": None,
                "bbox": None,
                "occurrence": None,
                "field_name": None,
                "value": None,
                "degrees": None,
                "font_size": None,
            },
            {
                "action": "replace_text",
                "page": 1,
                "target_text": "450000.00",
                "replacement_text": "455000.00",
                "text": None,
                "bbox": None,
                "occurrence": None,
                "field_name": None,
                "value": None,
                "degrees": None,
                "font_size": None,
            },
        ],
    }

    result = apply_pdf_edit_plan(source, plan)
    assessment = assess_pdf_edit_candidate(
        source,
        result.data,
        plan,
        visual_fidelity_score=result.visual_fidelity_score,
    )

    output = pymupdf.open(stream=result.data, filetype="pdf")
    page = output[0]
    assert "2306900.00" in page.get_text()
    assert "2150000.00" in page.get_text()
    assert "455000.00" in page.get_text()
    assert "1253181.00" not in page.get_text()
    assert "2105000.00" not in page.get_text()
    assert "450000.00" not in page.get_text()
    assert len(page.get_drawings()) >= 7
    output.close()

    assert result.verification_score == 100
    assert result.visual_fidelity_score == 100
    assert assessment.safe_to_return is True
    assert assessment.layout_integrity_score == 100
    assert assessment.issues == ()


def test_layout_gate_rejects_stacked_replacement_and_old_text_left_behind() -> None:
    source = _text_pdf("Salary: 1000")
    document = pymupdf.open(stream=source, filetype="pdf")
    document[0].insert_text((72, 44), "2000", fontsize=11)
    broken = document.tobytes()
    document.close()

    plan = {
        "summary": "Update salary",
        "operations": [
            {
                "action": "replace_text",
                "page": 1,
                "target_text": "1000",
                "replacement_text": "2000",
                "text": None,
                "bbox": None,
                "occurrence": None,
                "field_name": None,
                "value": None,
                "degrees": None,
                "font_size": None,
            }
        ],
    }

    assessment = assess_pdf_edit_candidate(source, broken, plan)

    assert assessment.safe_to_return is False
    assert assessment.layout_integrity_score < 100
    assert any("old text remains" in issue for issue in assessment.issues)
    assert any("drifted vertically" in issue for issue in assessment.issues)


def test_plan_validation_rejects_ambiguous_repeated_numeric_target() -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((60, 90), "HOUSE RENT ALLOWANCE", fontsize=10)
    page.insert_text((330, 90), "0", fontsize=10)
    page.insert_text((60, 120), "WIPRO BENEFITS PLAN", fontsize=10)
    page.insert_text((330, 120), "0", fontsize=10)
    source = document.tobytes()
    document.close()

    validation = validate_pdf_edit_plan(
        source,
        {
            "summary": "Change one allowance",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "0",
                    "replacement_text": "15000",
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

    assert validation.valid is False
    assert any("ambiguous with 2 matches" in issue for issue in validation.issues)
    assert any("occurrence or bbox" in issue for issue in validation.issues)


def test_plan_validation_rejects_overlapping_original_targets() -> None:
    document = pymupdf.open()
    page = document.new_page(width=500, height=300)
    page.insert_text((60, 100), "Annual package 2306900.00", fontsize=11)
    source = document.tobytes()
    document.close()

    validation = validate_pdf_edit_plan(
        source,
        {
            "summary": "Conflicting edits",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "Annual package 2306900.00",
                    "replacement_text": "Annual package 2400000.00",
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                },
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "2306900.00",
                    "replacement_text": "2400000.00",
                    "text": None,
                    "bbox": None,
                    "occurrence": None,
                    "field_name": None,
                    "value": None,
                    "degrees": None,
                    "font_size": None,
                },
            ],
        },
    )

    assert validation.valid is False
    assert any("overlap on page 1" in issue for issue in validation.issues)


def test_layout_gate_ignores_same_replacement_text_far_from_target() -> None:
    source_document = pymupdf.open()
    source_page = source_document.new_page(width=400, height=400)
    source_page.insert_text((60, 80), "Salary: 1000", fontsize=11)
    source_page.insert_text((60, 320), "Reference value: 2000", fontsize=11)
    source = source_document.tobytes()
    source_document.close()

    edited_document = pymupdf.open(stream=source, filetype="pdf")
    edited_page = edited_document[0]
    target = edited_page.search_for("1000")[0]
    edited_page.add_redact_annot(target, fill=False)
    edited_page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
    )
    broken = edited_document.tobytes()
    edited_document.close()

    plan = {
        "summary": "Update salary",
        "operations": [
            {
                "action": "replace_text",
                "page": 1,
                "target_text": "1000",
                "replacement_text": "2000",
                "text": None,
                "bbox": None,
                "occurrence": None,
                "field_name": None,
                "value": None,
                "degrees": None,
                "font_size": None,
            }
        ],
    }

    assessment = assess_pdf_edit_candidate(source, broken, plan)

    assert assessment.safe_to_return is False
    assert any(
        "replacement text is not detectable near the original target region" in issue
        for issue in assessment.issues
    )
    assert not any("drifted vertically" in issue for issue in assessment.issues)


def test_fidelity_accepts_embedded_font_alias_when_metrics_match() -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=220)
    page.insert_text(
        pymupdf.Point(100, 100),
        "ALIAS",
        fontname="helv",
        fontsize=14,
        color=(0.2, 0.3, 0.4),
    )
    target = page.search_for("ALIAS")[0]
    style = PDFTextStyle(
        font_name="ABCDEF+CorporateSans",
        font_size=14.0,
        color=(0.2, 0.3, 0.4),
        origin=(100.0, 100.0),
        line_rect=pymupdf.Rect(target),
        target_rect=pymupdf.Rect(target),
        alignment=pymupdf.TEXT_ALIGN_LEFT,
        rotation=0,
        font_alias="helv",
        font_buffer=None,
        exact_font_reusable=True,
    )

    score, note = _replacement_visual_fidelity(page, "ALIAS", style)
    document.close()

    assert score == 100
    assert "font=yes" in note
    assert "width=yes" in note
    assert "size=yes" in note
    assert "color=yes" in note
    assert "baseline=yes" in note
    assert "anchor=yes" in note


def test_fidelity_rejects_unknown_font_without_metric_equivalence() -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=220)
    page.insert_text(
        pymupdf.Point(100, 100),
        "DIFFERENT",
        fontname="helv",
        fontsize=14,
        color=(0.2, 0.3, 0.4),
    )
    target = page.search_for("DIFFERENT")[0]
    style = PDFTextStyle(
        font_name="ABCDEF+CorporateSans",
        font_size=14.0,
        color=(0.2, 0.3, 0.4),
        origin=(100.0, 100.0),
        line_rect=pymupdf.Rect(target),
        target_rect=pymupdf.Rect(target),
        alignment=pymupdf.TEXT_ALIGN_LEFT,
        rotation=0,
        font_alias="cour",
        font_buffer=None,
        exact_font_reusable=False,
    )

    score, note = _replacement_visual_fidelity(page, "DIFFERENT", style)
    document.close()

    assert score < 100
    assert "font=no" in note


def test_fidelity_uses_rgb_channel_tolerance_not_integer_distance() -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=220)
    page.insert_text(
        pymupdf.Point(90, 110),
        "COLOR",
        fontname="hebo",
        fontsize=12,
        color=(0.25, 0.5, 0.75),
    )
    target = page.search_for("COLOR")[0]
    style = PDFTextStyle(
        font_name="Helvetica-Bold",
        font_size=12.0,
        color=(0.25, 0.5, 0.75),
        origin=(90.0, 110.0),
        line_rect=pymupdf.Rect(target),
        target_rect=pymupdf.Rect(target),
        alignment=pymupdf.TEXT_ALIGN_LEFT,
        rotation=0,
        font_alias="hebo",
        font_buffer=None,
        exact_font_reusable=False,
    )

    score, note = _replacement_visual_fidelity(page, "COLOR", style)
    document.close()

    assert score == 100
    assert "color=yes" in note


def test_low_typography_fidelity_alone_does_not_make_layout_unsafe() -> None:
    source = _text_pdf("Invoice total: OLD")
    plan = {
        "summary": "Update total",
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
    }

    result = apply_pdf_edit_plan(source, plan)
    assessment = assess_pdf_edit_candidate(
        source,
        result.data,
        plan,
        visual_fidelity_score=83,
    )

    assert result.verification_score == 100
    assert assessment.safe_to_return is True
    assert assessment.layout_integrity_score == 100
    assert assessment.issues == ()
