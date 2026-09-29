"""48 kHz live voice styling that preserves the speaker's identity.

This built-in adapter intentionally does not clone another person's voice. It
provides optional model-free pitch shifting plus bounded tonal/dynamic styling
while keeping sample count, channel count, and packet duration unchanged.
"""

from __future__ import annotations

import asyncio
import math
import sys
from array import array
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock

from .live_profile_store import load_voice_style
from .openvoicechanger_pitch import PitchShifter


@dataclass
class _FilterState:
    previous_input: list[float]
    previous_low: list[float]
    pitch_shifters: list[PitchShifter]
    lock: Lock = field(default_factory=Lock)


_MAX_SESSION_STATES = 128
_STATES: OrderedDict[tuple[str, str, int], _FilterState] = OrderedDict()
_STATES_LOCK = Lock()


def _state_for(
    session_id: str,
    profile_id: str,
    channels: int,
    sample_rate_hz: int,
) -> _FilterState:
    key = (session_id, profile_id, channels)
    with _STATES_LOCK:
        state = _STATES.get(key)
        if state is None:
            state = _FilterState(
                previous_input=[0.0] * channels,
                previous_low=[0.0] * channels,
                pitch_shifters=[],
            )
            _STATES[key] = state
        _STATES.move_to_end(key)
        while len(_STATES) > _MAX_SESSION_STATES:
            _STATES.popitem(last=False)
        return state


def _decode_pcm16(payload: bytes) -> array:
    if not payload or len(payload) % 2:
        raise ValueError("voice adapter requires packed signed 16-bit PCM")
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _encode_pcm16(samples: array) -> bytes:
    if sys.byteorder == "little":
        return samples.tobytes()
    copy = array("h", samples)
    copy.byteswap()
    return copy.tobytes()


def _transform_sync(
    payload: bytes,
    profile_id: str,
    *,
    sample_rate_hz: int,
    channels: int,
    session_id: str,
) -> bytes:
    if sample_rate_hz != 48000 or channels not in (1, 2):
        raise ValueError("voice style adapter supports 48 kHz mono/stereo PCM")
    samples = _decode_pcm16(payload)
    if len(samples) % channels:
        raise ValueError("PCM payload is not aligned to the declared channel count")

    style = load_voice_style(profile_id)
    state = _state_for(session_id, profile_id, channels, sample_rate_hz)
    gain = 10.0 ** (style.gain_db / 20.0)
    normalizer = math.tanh(1.1)
    output = array("h")

    with state.lock:
        shifted = None
        if abs(style.pitch_semitones) >= 1e-3:
            import numpy as np

            if not state.pitch_shifters:
                state.pitch_shifters = [
                    PitchShifter(sample_rate_hz) for _ in range(channels)
                ]
            channel_audio = [
                np.asarray(samples[channel::channels], dtype=np.float32) / 32768.0
                for channel in range(channels)
            ]
            shifted = [
                state.pitch_shifters[channel].process(
                    channel_audio[channel], style.pitch_semitones
                )
                for channel in range(channels)
            ]

        for index, sample in enumerate(samples):
            channel = index % channels
            x = (
                float(sample) / 32768.0
                if shifted is None
                else float(shifted[channel][index // channels])
            )
            previous = state.previous_input[channel]
            low = 0.92 * state.previous_low[channel] + 0.08 * x
            high = x - previous
            shaped = x + style.presence * 0.22 * high + style.warmth * 0.16 * low
            shaped = math.tanh(shaped * gain * 1.1) / normalizer
            shaped = max(-1.0, min(0.999969, shaped))
            output.append(int(round(shaped * 32767.0)))
            state.previous_input[channel] = x
            state.previous_low[channel] = low

    result = _encode_pcm16(output)
    if len(result) != len(payload):
        raise RuntimeError("voice transform changed the live PCM duration")
    return result


async def prepare_profile(profile_id: str) -> None:
    """Validate the authorized voice-style profile before session admission."""
    await asyncio.to_thread(load_voice_style, profile_id)


async def transform_voice(
    payload: bytes,
    profile_id: str,
    *,
    media_metadata: dict[str, object] | None = None,
) -> bytes:
    metadata = media_metadata or {}
    sample_rate = metadata.get("sample_rate_hz")
    channels = metadata.get("channels")
    session_id = metadata.get("session_id")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError("voice adapter requires a live session id")
    if type(sample_rate) is not int or type(channels) is not int:
        raise ValueError("voice adapter requires sample rate and channel metadata")
    return await asyncio.to_thread(
        _transform_sync,
        payload,
        profile_id,
        sample_rate_hz=sample_rate,
        channels=channels,
        session_id=session_id,
    )
