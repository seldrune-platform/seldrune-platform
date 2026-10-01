import asyncio
import hashlib
import json

import numpy as np
import pytest

from services.live_media import live_profile_store, seedvc_voice_adapter


def _provision_voice_reference(tmp_path, monkeypatch, profile_id="approved-voice"):
    root = tmp_path / "profiles"
    directory = root / profile_id
    directory.mkdir(parents=True)
    audio = b"synthetic test audio payload"
    (directory / "reference.wav").write_bytes(audio)
    (directory / "voice-reference.json").write_text(
        json.dumps(
            {
                "filename": "reference.wav",
                "sha256": hashlib.sha256(audio).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SELDRUNE_LIVE_PROFILE_ROOT", str(root))
    return directory


class IdentityEngine:
    def __init__(self):
        self.blocks = []

    def prepare(self, profile_id, reference_path):
        assert profile_id == "approved-voice"
        assert reference_path.is_file()
        return np.full(22_050, 0.1, dtype=np.float32)

    def convert_block(self, reference_path, reference_audio, state, source_block_48k):
        self.blocks.append(source_block_48k.copy())
        return source_block_48k.copy()


def test_voice_reference_manifest_checks_digest_and_stays_in_profile(
    tmp_path, monkeypatch
):
    directory = _provision_voice_reference(tmp_path, monkeypatch)

    path, digest = live_profile_store.resolve_voice_reference("approved-voice")

    assert path == directory / "reference.wav"
    assert digest == hashlib.sha256(b"synthetic test audio payload").hexdigest()


def test_voice_reference_rejects_path_traversal_and_digest_mismatch(
    tmp_path, monkeypatch
):
    directory = _provision_voice_reference(tmp_path, monkeypatch)
    manifest_path = directory / "voice-reference.json"
    manifest_path.write_text(
        json.dumps({"filename": "../reference.wav", "sha256": "0" * 64}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="manifest entry"):
        live_profile_store.resolve_voice_reference("approved-voice")

    (directory / "reference.wav").write_bytes(b"changed audio")
    manifest_path.write_text(
        json.dumps(
            {
                "filename": "reference.wav",
                "sha256": hashlib.sha256(b"original audio").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="digest"):
        live_profile_store.resolve_voice_reference("approved-voice")


def test_seedvc_streaming_buffers_240ms_and_preserves_pcm_duration(
    tmp_path, monkeypatch
):
    _provision_voice_reference(tmp_path, monkeypatch)
    engine = IdentityEngine()
    adapter = seedvc_voice_adapter.SeedVCVoiceAdapter(engine=engine)
    packet = (np.full(960, 5000, dtype="<i2")).tobytes()

    async def run():
        await adapter.prepare_profile("approved-voice")
        outputs = []
        for sequence in range(12):
            outputs.append(
                await adapter.transform_voice(
                    packet,
                    "approved-voice",
                    media_metadata={
                        "session_id": "session-1",
                        "sample_rate_hz": 48_000,
                        "channels": 1,
                        "sequence": sequence,
                    },
                )
            )
        return outputs

    outputs = asyncio.run(run())

    assert all(len(output) == len(packet) for output in outputs)
    assert len(engine.blocks) == 1
    assert engine.blocks[0].size == 48_000 * 240 // 1000
    assert any(outputs[-1])


def test_seedvc_streaming_returns_aligned_stereo_pcm(tmp_path, monkeypatch):
    _provision_voice_reference(tmp_path, monkeypatch)
    engine = IdentityEngine()
    adapter = seedvc_voice_adapter.SeedVCVoiceAdapter(engine=engine)
    mono = np.full(960, 4500, dtype="<i2")
    packet = np.column_stack((mono, -mono)).astype("<i2").tobytes()

    async def run():
        await adapter.prepare_profile("approved-voice")
        outputs = []
        for sequence in range(12):
            outputs.append(
                await adapter.transform_voice(
                    packet,
                    "approved-voice",
                    media_metadata={
                        "session_id": "stereo-session",
                        "sample_rate_hz": 48_000,
                        "channels": 2,
                        "sequence": sequence,
                    },
                )
            )
        return outputs

    outputs = asyncio.run(run())
    last = np.frombuffer(outputs[-1], dtype="<i2").reshape(-1, 2)

    assert all(len(output) == len(packet) for output in outputs)
    assert engine.blocks[0].size == 48_000 * 240 // 1000
    assert np.array_equal(last[:, 0], last[:, 1])


def test_seedvc_requires_approved_profile_and_supported_audio_metadata():
    adapter = seedvc_voice_adapter.SeedVCVoiceAdapter(engine=IdentityEngine())
    packet = np.zeros(960, dtype="<i2").tobytes()

    async def run():
        with pytest.raises(RuntimeError, match="must be prepared"):
            await adapter.transform_voice(
                packet,
                "unapproved",
                media_metadata={
                    "session_id": "session-2",
                    "sample_rate_hz": 48_000,
                    "channels": 1,
                },
            )
        with pytest.raises(ValueError, match="48 kHz"):
            await adapter.transform_voice(
                packet,
                "approved-voice",
                media_metadata={
                    "session_id": "session-2",
                    "sample_rate_hz": 44_100,
                    "channels": 1,
                },
            )

    asyncio.run(run())
