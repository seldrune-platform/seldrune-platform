"""Tests for the bounded paired training loop."""
import pytest

from services.live_media.face_paired_loop import run_paired_loop


def test_paired_loop_rejects_empty_batches() -> None:
    with pytest.raises(ValueError, match="requires batches"):
        run_paired_loop(object(), object(), (), device="cuda", max_steps=1)
