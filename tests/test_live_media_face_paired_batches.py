"""Tests for source/reference pairing without external face-swap weights."""
from types import SimpleNamespace
import pytest
from services.live_media.face_paired_batches import build_paired_batches

def test_paired_batches_reject_empty_dataset() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_paired_batches([], batch_size=1)

def test_paired_batches_reject_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_paired_batches([], batch_size=0)
