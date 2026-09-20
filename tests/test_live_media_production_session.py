"""Tests for fail-closed production-session orchestration."""

import asyncio

import pytest

from services.live_media.face_production_recorder import FaceProductionRecorder
from services.live_media.production_session import record_production_session


def _recorder(tmp_path) -> FaceProductionRecorder:
    receipt = tmp_path / "verification.json"
    receipt.write_text("verified", encoding="utf-8")
    return FaceProductionRecorder(
        run_id="production-session",
        verification_receipt_path=receipt,
        output_width=1280,
        output_height=720,
        audio_sample_rate_hz=None,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )


def test_failed_session_removes_stale_evidence(tmp_path) -> None:
    output = tmp_path / "production.json"
    output.write_text("stale", encoding="utf-8")

    async def fail(_recorder):
        raise RuntimeError("transport failed")

    with pytest.raises(RuntimeError, match="transport failed"):
        asyncio.run(record_production_session(_recorder(tmp_path), fail, output_path=output))

    assert not output.exists()


def test_cancelled_session_removes_stale_evidence(tmp_path) -> None:
    output = tmp_path / "production.json"
    output.write_text("stale", encoding="utf-8")

    async def cancel(_recorder):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(record_production_session(_recorder(tmp_path), cancel, output_path=output))

    assert not output.exists()


def test_invalid_completed_session_writes_no_evidence(tmp_path) -> None:
    output = tmp_path / "production.json"

    async def empty(_recorder):
        return None

    with pytest.raises(ValueError, match="no transformed frames"):
        asyncio.run(record_production_session(_recorder(tmp_path), empty, output_path=output))

    assert not output.exists()
