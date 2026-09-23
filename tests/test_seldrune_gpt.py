def test_seldrune_gpt_requires_auth(client):
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt",
        json={"message": "hello"},
    )
    assert response.status_code in {401, 403}


def test_gpt_response_schema_exposes_runtime_metadata():
    from backend.app.api.routes.seldrune_gpt import SeldruneGPTResponse

    response = SeldruneGPTResponse(
        model="test-model",
        response="hello",
        response_id="resp_1",
        input_tokens=3,
        output_tokens=4,
        latency_ms=12,
        provider="openai",
    )
    assert response.model == "test-model"
    assert response.latency_ms == 12
    assert response.provider == "openai"


def test_gpt_attachment_parser_accepts_image_and_pdf() -> None:
    import base64

    from backend.app.api.routes.seldrune_gpt import (
        SeldruneGPTAttachment,
        _model_attachments,
    )

    encoded = base64.b64encode(b"hello").decode("ascii")
    images, files, names = _model_attachments(
        [
            SeldruneGPTAttachment(
                name="diagram.png",
                media_type="image/png",
                data_base64=encoded,
            ),
            SeldruneGPTAttachment(
                name="brief.pdf",
                media_type="application/pdf",
                data_base64=encoded,
            ),
        ]
    )
    assert names == ["diagram.png", "brief.pdf"]
    assert len(images) == 1
    assert images[0].name == "diagram.png"
    assert len(files) == 1
    assert files[0].filename == "brief.pdf"


def test_gpt_attachment_parser_rejects_unsupported_type() -> None:
    import base64

    import pytest
    from fastapi import HTTPException

    from backend.app.api.routes.seldrune_gpt import (
        SeldruneGPTAttachment,
        _model_attachments,
    )

    encoded = base64.b64encode(b"hello").decode("ascii")
    with pytest.raises(HTTPException) as exc_info:
        _model_attachments(
            [
                SeldruneGPTAttachment(
                    name="binary.exe",
                    media_type="application/x-msdownload",
                    data_base64=encoded,
                )
            ]
        )
    assert exc_info.value.status_code == 422


def test_pdf_editor_replaces_existing_text() -> None:
    import pymupdf

    from backend.app.api.routes.seldrune_gpt import _apply_pdf_edit_plan

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Invoice date: 2025-09-23")
    source = document.tobytes()
    document.close()

    edited, applied, warnings = _apply_pdf_edit_plan(
        source,
        {
            "summary": "Updated invoice date.",
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "2025-09-23",
                    "replacement_text": "2026-09-23",
                    "text": None,
                }
            ],
        },
    )

    output = pymupdf.open(stream=edited, filetype="pdf")
    text = output[0].get_text()
    output.close()

    assert applied == 1
    assert warnings == []
    assert "2026-09-23" in text
    assert "2025-09-23" not in text


def test_pdf_editor_rejects_plan_when_target_is_missing() -> None:
    import pymupdf
    import pytest
    from fastapi import HTTPException

    from backend.app.api.routes.seldrune_gpt import _apply_pdf_edit_plan

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Hello Seldrune")
    source = document.tobytes()
    document.close()

    with pytest.raises(HTTPException) as exc_info:
        _apply_pdf_edit_plan(
            source,
            {
                "summary": "Change missing text.",
                "operations": [
                    {
                        "action": "replace_text",
                        "page": 1,
                        "target_text": "Not in document",
                        "replacement_text": "Replacement",
                        "text": None,
                    }
                ],
            },
        )

    assert exc_info.value.status_code == 422


def test_advanced_pdf_editor_verifies_text_replacement() -> None:
    import pymupdf

    from backend.app.services.pdf_editor import apply_advanced_pdf_edit_plan

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Member ID: ABC123")
    source = document.tobytes()
    document.close()

    edited, applied, verified, warnings, verification = apply_advanced_pdf_edit_plan(
        source,
        {
            "operations": [
                {
                    "action": "replace_text",
                    "page": 1,
                    "target_text": "ABC123",
                    "replacement_text": "XYZ789",
                    "text": None,
                    "rect_norm": None,
                    "font_size": None,
                    "text_color": None,
                    "background_color": None,
                    "alignment": "left",
                    "field_name": None,
                    "field_value": None,
                    "rotation": None,
                }
            ]
        },
    )

    output = pymupdf.open(stream=edited, filetype="pdf")
    text = output[0].get_text("text")
    output.close()

    assert applied == 1
    assert verified == 1
    assert verification[0]["verified"] is True
    assert "XYZ789" in text
    assert "ABC123" not in text
    assert not [item for item in warnings if "Verification failed" in item]


def test_advanced_pdf_editor_visual_fallback_adds_text_layer() -> None:
    import pymupdf

    from backend.app.services.pdf_editor import apply_advanced_pdf_edit_plan

    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.draw_rect(
        pymupdf.Rect(40, 90, 360, 150),
        color=None,
        fill=(0.94, 0.94, 0.94),
    )
    source = document.tobytes()
    document.close()

    edited, applied, verified, _warnings, verification = apply_advanced_pdf_edit_plan(
        source,
        {
            "operations": [
                {
                    "action": "visual_replace",
                    "page": 1,
                    "target_text": None,
                    "replacement_text": "Scanned document correction",
                    "text": None,
                    "rect_norm": [0.1, 0.3, 0.9, 0.5],
                    "font_size": 12,
                    "text_color": [0, 0, 0],
                    "background_color": [0.94, 0.94, 0.94],
                    "alignment": "center",
                    "field_name": None,
                    "field_value": None,
                    "rotation": None,
                }
            ]
        },
    )

    output = pymupdf.open(stream=edited, filetype="pdf")
    text = output[0].get_text("text")
    output.close()

    assert applied == 1
    assert verified == 1
    assert verification[0]["verified"] is True
    assert "Scanned document correction" in text


def test_advanced_pdf_editor_updates_form_field() -> None:
    import pymupdf

    from backend.app.services.pdf_editor import apply_advanced_pdf_edit_plan

    document = pymupdf.open()
    page = document.new_page()
    widget = pymupdf.Widget()
    widget.field_name = "customer_name"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 72, 260, 100)
    page.add_widget(widget)
    source = document.tobytes()
    document.close()

    edited, applied, verified, _warnings, verification = apply_advanced_pdf_edit_plan(
        source,
        {
            "operations": [
                {
                    "action": "set_form_field",
                    "page": 1,
                    "target_text": None,
                    "replacement_text": None,
                    "text": None,
                    "rect_norm": None,
                    "font_size": None,
                    "text_color": None,
                    "background_color": None,
                    "alignment": None,
                    "field_name": "customer_name",
                    "field_value": "Seldrune Owner",
                    "rotation": None,
                }
            ]
        },
    )

    output = pymupdf.open(stream=edited, filetype="pdf")
    output_widget = output[0].first_widget
    assert output_widget is not None
    value = output_widget.field_value
    output.close()

    assert applied == 1
    assert verified == 1
    assert verification[0]["verified"] is True
    assert value == "Seldrune Owner"


def test_pdf_visual_context_detects_image_dominant_page() -> None:
    import pymupdf

    from backend.app.services.pdf_editor import build_pdf_visual_context

    document = pymupdf.open()
    document.new_page(width=320, height=240)
    source = document.tobytes()
    document.close()

    context = build_pdf_visual_context(source, max_rendered_pages=2)

    assert context.scanned_pages == (1,)
    assert context.rendered_pages == (1,)
    assert len(context.images) == 1
    assert context.images[0].media_type == "image/jpeg"
    assert "page=1" in context.profile_text
