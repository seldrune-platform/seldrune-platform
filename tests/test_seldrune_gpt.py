def test_seldrune_gpt_requires_auth(client):
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt",
        json={"message": "hello"},
    )
    assert response.status_code in {401, 403}


def test_seldrune_gpt_media_requires_auth(client):
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/media",
        json={"kind": "image", "prompt": "A blue mountain at sunrise"},
    )
    assert response.status_code in {401, 403}


def test_seldrune_gpt_pdf_create_requires_auth(client):
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/pdf/create",
        json={"title": "Sample report", "content": "A readable PDF."},
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


def test_gpt_request_accepts_explicit_openai_model() -> None:
    from backend.app.api.routes.seldrune_gpt import SeldruneGPTRequest

    request = SeldruneGPTRequest(
        message="Review this Seldrune deployment.",
        provider="openai",
        model="gpt-6-astra",
    )

    assert request.model == "gpt-6-astra"
    assert request.provider == "openai"


def test_gpt_media_request_accepts_product_modes_and_bounded_prompt() -> None:
    from backend.app.api.routes.seldrune_gpt import SeldruneGPTMediaRequest

    image = SeldruneGPTMediaRequest(kind="image", prompt="A moonlit mountain")
    speech = SeldruneGPTMediaRequest(kind="speech", prompt="Welcome to Seldrune.")
    video = SeldruneGPTMediaRequest(kind="video", prompt="A short forest scene")

    assert image.kind == "image"
    assert speech.kind == "speech"
    assert video.kind == "video"


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


def test_gpt_request_accepts_conversation_id() -> None:
    from uuid import UUID

    from backend.app.api.routes.seldrune_gpt import SeldruneGPTRequest

    conversation_id = UUID("00000000-0000-0000-0000-000000000123")
    request = SeldruneGPTRequest(
        message="Continue this chat.",
        conversation_id=conversation_id,
    )

    assert request.conversation_id == conversation_id


def test_gpt_conversation_summary_supports_legacy_history() -> None:
    from backend.app.api.routes.seldrune_gpt import SeldruneGPTConversationSummary

    summary = SeldruneGPTConversationSummary(
        id=None,
        title="Earlier saved history",
        updated_at=None,
        legacy=True,
    )

    assert summary.id is None
    assert summary.legacy is True


def test_gpt_request_accepts_intelligent_ui_prompt() -> None:
    from backend.app.api.routes.seldrune_gpt import SeldruneGPTRequest

    request = SeldruneGPTRequest(
        message="Create a small project dashboard.",
        intelligent_ui=True,
        openui_prompt="OpenUI Lang component and syntax instructions.",
    )

    assert request.intelligent_ui is True
    assert request.openui_prompt.startswith("OpenUI Lang")


def test_openui_response_is_marked_and_fences_are_removed() -> None:
    from backend.app.api.routes.seldrune_gpt import (
        OPENUI_RESPONSE_MARKER,
        _mark_openui_response,
    )

    response = _mark_openui_response("```openui\nroot = Card([])\n```")

    assert response == OPENUI_RESPONSE_MARKER + "\nroot = Card([])"
