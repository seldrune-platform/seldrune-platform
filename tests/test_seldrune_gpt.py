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
