"""Tests for authorized single-frame and continuous Face execution."""

from dataclasses import replace

import pytest

from services.live_media.face_stream_runner import run_face_stream
from services.live_media.face_training_executor import sha256_file
from services.live_media.face_transform_runner import FaceTransformRequest, run_face_transform


class DeterministicBackend:
    def transform(self, source_frame: bytes, reference_image: bytes) -> bytes:
        return b"seldrune-transformed:" + source_frame + b":" + reference_image


class UnchangedBackend:
    def transform(self, source_frame: bytes, reference_image: bytes) -> bytes:
        return source_frame


def _file(path, content: bytes):
    path.write_bytes(content)
    return path


def _request(tmp_path) -> FaceTransformRequest:
    return FaceTransformRequest(
        model_path=_file(tmp_path / "face.onnx", b"trained-model"),
        source_frame_path=_file(tmp_path / "source.bin", b"source-frame"),
        reference_image_path=_file(tmp_path / "reference.bin", b"authorized-reference"),
        output_frame_path=tmp_path / "output.bin",
        authorization_verified=True,
        synthetic_media_indicator_enabled=True,
    )


def test_transform_persists_changed_frame_and_real_hashes(tmp_path) -> None:
    request = _request(tmp_path)
    result = run_face_transform(request, DeterministicBackend())
    assert result.output_path.is_file()
    assert result.evidence.model_sha256 == sha256_file(request.model_path)
    assert result.evidence.input_sha256 == sha256_file(request.source_frame_path)
    assert result.evidence.output_sha256 == sha256_file(result.output_path)
    assert result.evidence.input_sha256 != result.evidence.output_sha256


def test_transform_blocks_unauthorized_or_undisclosed_use(tmp_path) -> None:
    request = _request(tmp_path)
    with pytest.raises(ValueError, match="authorized identity"):
        run_face_transform(replace(request, authorization_verified=False), DeterministicBackend())
    with pytest.raises(ValueError, match="indicator"):
        run_face_transform(
            replace(request, synthetic_media_indicator_enabled=False),
            DeterministicBackend(),
        )


def test_transform_rejects_unchanged_output(tmp_path) -> None:
    with pytest.raises(ValueError, match="unchanged"):
        run_face_transform(_request(tmp_path), UnchangedBackend())


def test_stream_returns_measured_evidence_for_every_frame(tmp_path) -> None:
    model = _file(tmp_path / "face.onnx", b"trained-model")
    reference = _file(tmp_path / "reference.bin", b"authorized-reference")
    frames = tuple(
        _file(tmp_path / f"source-{index}.bin", f"frame-{index}".encode())
        for index in range(3)
    )
    result = run_face_stream(
        model_path=model,
        source_frames=frames,
        reference_image_path=reference,
        output_dir=tmp_path / "output",
        backend=DeterministicBackend(),
        authorization_verified=True,
        synthetic_media_indicator_enabled=True,
    )
    assert result.evidence.frames_processed == 3
    assert result.evidence.frames_transformed == 3
    assert len(result.frames) == 3
