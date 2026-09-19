"""Tests for verifiable Face GPU training receipts."""
from datetime import UTC, datetime, timedelta

import pytest

from services.live_media.face_gpu_receipt import (
    GpuExecutionState,
    GpuTrainingReceipt,
)


def _receipt(**overrides: object) -> GpuTrainingReceipt:
    started = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)
    values = {
        "job_id": "face-job-001",
        "execution_digest": "a" * 64,
        "model_version": "seldrune-face-v0.1",
        "accelerator": "rtx-pro-6000-blackwell",
        "dataset_manifest_sha256": "b" * 64,
        "started_at": started,
        "completed_at": started + timedelta(minutes=5),
        "final_step": 10,
        "checkpoint_sha256": ("c" * 64,),
        "state": GpuExecutionState.SUCCEEDED,
        "error": None,
    }
    values.update(overrides)
    return GpuTrainingReceipt(**values)


def test_success_receipt_validates() -> None:
    _receipt().validate()


def test_success_requires_checkpoint_evidence() -> None:
    with pytest.raises(ValueError):
        _receipt(checkpoint_sha256=()).validate()


def test_failed_receipt_requires_error() -> None:
    with pytest.raises(ValueError):
        _receipt(state=GpuExecutionState.FAILED, final_step=0, checkpoint_sha256=()).validate()


def test_failed_receipt_with_error_validates() -> None:
    _receipt(
        state=GpuExecutionState.FAILED,
        final_step=0,
        checkpoint_sha256=(),
        error="worker interrupted",
    ).validate()


def test_receipt_rejects_bad_digest() -> None:
    with pytest.raises(ValueError):
        _receipt(execution_digest="bad").validate()


def test_receipt_rejects_reversed_timestamps() -> None:
    started = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        _receipt(completed_at=started - timedelta(seconds=1)).validate()
