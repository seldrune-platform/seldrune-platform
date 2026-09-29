from array import array
from types import SimpleNamespace
import uuid

import numpy as np

from services.live_media import voice_style_adapter


def _dominant_frequency(samples: array, sample_rate: int) -> float:
    audio = np.asarray(samples, dtype=np.float32)
    spectrum = np.abs(np.fft.rfft(audio))
    frequencies = np.fft.rfftfreq(len(audio), 1.0 / sample_rate)
    return float(frequencies[int(np.argmax(spectrum))])


def test_voice_profile_pitch_shift_preserves_duration_and_changes_tone(monkeypatch):
    sample_rate = 48_000
    chunk_size = 960
    frequency = 220.0
    sample_count = sample_rate * 2
    source = array(
        "h",
        (
            int(7000 * np.sin(2 * np.pi * frequency * index / sample_rate))
            for index in range(sample_count)
        ),
    )
    profile = SimpleNamespace(
        gain_db=0.0,
        presence=0.0,
        warmth=0.0,
        pitch_semitones=4.0,
    )
    monkeypatch.setattr(voice_style_adapter, "load_voice_style", lambda _: profile)

    session_id = "voice-test-" + uuid.uuid4().hex
    output = array("h")
    for start in range(0, sample_count, chunk_size):
        output.frombytes(
            voice_style_adapter._transform_sync(
                source[start:start + chunk_size].tobytes(),
                "approved-voice",
                sample_rate_hz=sample_rate,
                channels=1,
                session_id=session_id,
            )
        )

    assert len(output) == len(source)
    measured = _dominant_frequency(output[sample_rate // 2:], sample_rate)
    assert 250.0 < measured < 300.0
