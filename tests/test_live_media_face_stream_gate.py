"""Tests for continuous Face stream evidence."""
import pytest

from services.live_media.face_stream_gate import FaceStreamEvidence


def test_stream_requires_multiple_frames() -> None:
    with pytest.raises(ValueError, match="multiple"):
        FaceStreamEvidence(1, 1, 1.0, 10.0).validate()
