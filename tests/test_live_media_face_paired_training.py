"""Tests for paired Face training contracts."""
import pytest

from services.live_media.face_paired_training import PairedTrainingBatch


def test_paired_batch_rejects_missing_tensor() -> None:
    with pytest.raises(ValueError, match="required"):
        PairedTrainingBatch(None, object(), object()).validate()
