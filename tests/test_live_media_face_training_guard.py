"""Tests for Face real-training admission."""
import pytest

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_training_guard import admit_face_training
from services.live_media.face_training_bundle import FaceTrainingBundle


def test_empty_bundle_is_not_admitted() -> None:
    execution = GpuTrainingExecution("job", "seldrune-face-v0.1", "gpu", "a" * 64, 1, 1, "bf16", "/tmp")
    with pytest.raises(ValueError):
        admit_face_training(execution, FaceTrainingBundle((), {}))
