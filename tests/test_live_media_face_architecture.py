from services.live_media.face_architecture import (
    FaceArchitecture,
    default_face_architecture,
)


def test_default_face_architecture_is_identity_conditioned_rgb() -> None:
    architecture = default_face_architecture()
    assert architecture.input_channels == 3
    assert architecture.output_channels == 3
    assert architecture.identity_embedding_dim == 512


def test_face_architecture_rejects_non_rgb_output() -> None:
    architecture = FaceArchitecture(output_channels=4)
    try:
        architecture.validate()
    except ValueError as exc:
        assert "RGB" in str(exc)
    else:
        raise AssertionError("invalid architecture was accepted")
