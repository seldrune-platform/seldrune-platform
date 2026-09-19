"""Tests for file-backed Face verification evidence collection."""

from dataclasses import replace

import pytest

from services.live_media.face_evidence_collector import (
    FaceEvidenceFiles,
    FaceMeasuredMetrics,
    collect_verification_receipt,
)
from services.live_media.face_training_executor import sha256_file


def _write(path, content: bytes):
    path.write_bytes(content)
    return path


def _files(tmp_path) -> FaceEvidenceFiles:
    return FaceEvidenceFiles(
        checkpoint=_write(tmp_path / "checkpoint.pt", b"trained-checkpoint"),
        onnx_model=_write(tmp_path / "face.onnx", b"exported-onnx-model"),
        input_frame=_write(tmp_path / "input.png", b"source-frame"),
        output_frame=_write(tmp_path / "output.png", b"transformed-frame"),
        reference_image=_write(tmp_path / "reference.png", b"authorized-reference"),
    )


def _metrics() -> FaceMeasuredMetrics:
    return FaceMeasuredMetrics(
        inference_ms=18.0,
        identity_similarity=0.88,
        frame_change_ratio=0.22,
        frames_processed=120,
        frames_transformed=118,
        stream_duration_seconds=4.0,
        average_inference_ms=19.0,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )


def test_collector_hashes_real_evidence_files(tmp_path) -> None:
    files = _files(tmp_path)
    receipt = collect_verification_receipt(
        run_id="gpu-run-001",
        model_version="seldrune-face-v0.1",
        dataset_manifest_sha256="a" * 64,
        files=files,
        metrics=_metrics(),
    )
    assert receipt.output.checkpoint_sha256 == sha256_file(files.checkpoint)
    assert receipt.output.onnx_sha256 == sha256_file(files.onnx_model)
    assert receipt.inference.input_sha256 == sha256_file(files.input_frame)
    assert receipt.inference.output_sha256 == sha256_file(files.output_frame)
    assert receipt.reference_sha256 == sha256_file(files.reference_image)


def test_collector_rejects_missing_or_empty_evidence(tmp_path) -> None:
    files = _files(tmp_path)
    files.output_frame.unlink()
    with pytest.raises(ValueError, match="missing"):
        files.validate()
    empty = _write(tmp_path / "output.png", b"")
    with pytest.raises(ValueError, match="empty"):
        replace(files, output_frame=empty).validate()


def test_collector_rejects_identical_input_and_output(tmp_path) -> None:
    files = _files(tmp_path)
    files.output_frame.write_bytes(files.input_frame.read_bytes())
    with pytest.raises(ValueError, match="differ"):
        collect_verification_receipt(
            run_id="gpu-run-001",
            model_version="seldrune-face-v0.1",
            dataset_manifest_sha256="a" * 64,
            files=files,
            metrics=_metrics(),
        )


def test_collector_rejects_unverified_authorization(tmp_path) -> None:
    with pytest.raises(ValueError, match="authorized identity"):
        collect_verification_receipt(
            run_id="gpu-run-001",
            model_version="seldrune-face-v0.1",
            dataset_manifest_sha256="a" * 64,
            files=_files(tmp_path),
            metrics=replace(_metrics(), authorization_verified=False),
        )
