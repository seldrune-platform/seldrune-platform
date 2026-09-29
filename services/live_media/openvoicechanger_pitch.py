"""Streaming pitch shifter adapted from OpenVoiceChanger's DSP effects.

Copyright (c) 2024 Sioaeko. Licensed under the MIT License; see
OPENVOICECHANGER-LICENSE in this directory.
"""

from typing import Any


def _numpy() -> Any:
    try:
        import numpy
    except ImportError as exc:
        raise RuntimeError("Live voice pitch shifting requires NumPy on the media worker") from exc
    return numpy


class PitchShifter:
    """Continuous dual-tap delay-line pitch shifter.

    Adapted from OpenVoiceChanger/backend/services/dsp_effects.py at commit
    8e6a00c628eafc0fd1d68c6bc13f2c17b8a46ea1. It keeps a short input history
    and crossfades two moving taps so independent audio packets remain smooth.
    """

    WINDOW_SECONDS = 0.032

    def __init__(self, sample_rate: int) -> None:
        self._np = _numpy()
        self.sr = int(sample_rate)
        self.win = max(64, int(self.WINDOW_SECONDS * self.sr))
        self._hist = self._np.zeros(self.win + 2, dtype=self._np.float32)
        self._phase = 0.0

    def process(self, audio: Any, semitones: float) -> Any:
        np = self._np
        if abs(semitones) < 1e-3 or len(audio) == 0:
            self._push_history(audio)
            return audio

        ratio = 2.0 ** (semitones / 12.0)
        count = len(audio)
        rate = 1.0 - ratio
        indices = np.arange(count, dtype=np.float64)
        delay_a = (self._phase + rate * indices) % self.win
        self._phase = float((self._phase + rate * count) % self.win)
        delay_b = (delay_a + self.win / 2.0) % self.win
        gain_a = np.sin(np.pi * delay_a / self.win)
        gain_b = np.sin(np.pi * delay_b / self.win)

        full = np.concatenate([self._hist, audio.astype(np.float32)])
        positions = np.arange(len(full), dtype=np.float64)
        write_position = len(self._hist) + indices
        tap_a = np.interp(write_position - delay_a, positions, full)
        tap_b = np.interp(write_position - delay_b, positions, full)

        self._hist = full[-(self.win + 2):]
        return (gain_a * tap_a + gain_b * tap_b).astype(np.float32)

    def _push_history(self, audio: Any) -> None:
        np = self._np
        if len(audio) == 0:
            return
        full = np.concatenate([self._hist, audio.astype(np.float32)])
        self._hist = full[-(self.win + 2):]
