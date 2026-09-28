"""Rolling post-transform evaluators for final LiveShell outbound media.

Video evidence is measured after the visible synthetic-media label is rendered.
The built-in audio path is a same-speaker style transform, not voice cloning; its
"speaker_similarity" score is an input/output preservation proxy and is named as
such by evaluator_id so it is not confused with a biometric target-speaker claim.
"""

from __future__ import annotations

import io
import math
import os
import sys
from array import array
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .live_profile_store import resolve_face_reference
from .realism_quality_gate import (
    FaceRealismEvidence,
    FaceRealismWarmupEvidence,
    VoiceRealismEvidence,
    VoiceRealismWarmupEvidence,
)

_FACE_WINDOW = int(os.getenv("SELDRUNE_LIVE_FACE_WINDOW_FRAMES", "30"))
_VOICE_WINDOW_SECONDS = float(
    os.getenv("SELDRUNE_LIVE_VOICE_WINDOW_SECONDS", "1.0")
)
_FACEFUSION_ROOT = Path(os.getenv("FACEFUSION_ROOT", "/opt/facefusion")).resolve()


def _clamp_score(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _percentile95(values: deque[float]) -> float:
    if not values:
        return 0.001
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1))
    return max(float(ordered[index]), 0.001)


@dataclass
class _FaceWindowState:
    identities: deque[float] = field(default_factory=lambda: deque(maxlen=_FACE_WINDOW))
    temporal: deque[float] = field(default_factory=lambda: deque(maxlen=_FACE_WINDOW))
    blend: deque[float] = field(default_factory=lambda: deque(maxlen=_FACE_WINDOW))
    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=_FACE_WINDOW))
    previous_embedding: object | None = None


@dataclass
class _VoiceChunk:
    sample_count: int
    speaker_preservation: float
    content_preservation: float
    naturalness: float
    clipped_fraction: float
    dropout_fraction: float
    processing_ms: float


@dataclass
class _VoiceWindowState:
    chunks: deque[_VoiceChunk] = field(default_factory=deque)
    total_samples: int = 0


# Bound state across completed sessions while keeping every live-session window isolated.
_MAX_SESSION_STATE_ENTRIES = 128
_FACE_STATES: OrderedDict[tuple[str, str], _FaceWindowState] = OrderedDict()
_VOICE_STATES: OrderedDict[tuple[str, str, int, int], _VoiceWindowState] = OrderedDict()


def _require_session_id(media_metadata: dict[str, object]) -> str:
    session_id = media_metadata.get("session_id")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError("quality evaluator requires a live session id")
    return session_id


def _face_window_state(session_id: str, profile_id: str) -> _FaceWindowState:
    key = (session_id, profile_id)
    state = _FACE_STATES.get(key)
    if state is None:
        state = _FaceWindowState()
        _FACE_STATES[key] = state
    _FACE_STATES.move_to_end(key)
    while len(_FACE_STATES) > _MAX_SESSION_STATE_ENTRIES:
        _FACE_STATES.popitem(last=False)
    return state


def _voice_window_state(
    session_id: str, profile_id: str, sample_rate: int, channels: int
) -> _VoiceWindowState:
    key = (session_id, profile_id, sample_rate, channels)
    state = _VOICE_STATES.get(key)
    if state is None:
        state = _VoiceWindowState()
        _VOICE_STATES[key] = state
    _VOICE_STATES.move_to_end(key)
    while len(_VOICE_STATES) > _MAX_SESSION_STATE_ENTRIES:
        _VOICE_STATES.popitem(last=False)
    return state


def _ensure_facefusion_import_path() -> None:
    if not _FACEFUSION_ROOT.is_dir():
        raise RuntimeError("FaceFusion runtime is not installed")
    root = str(_FACEFUSION_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _decode_bgr(payload: bytes):
    import numpy as np

    try:
        with Image.open(io.BytesIO(payload)) as source:
            rgb = np.asarray(source.convert("RGB"))
    except OSError as exc:
        raise ValueError("face evaluator requires a decodable final JPEG") from exc
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("face evaluator requires three-channel video output")
    return np.ascontiguousarray(rgb[:, :, ::-1])


def _face_measurements(payload: bytes, profile_id: str) -> tuple[float, float, object]:
    import numpy as np

    _ensure_facefusion_import_path()
    from facefusion.face_creator import get_one_face, get_static_faces
    from facefusion.vision import read_static_image

    profile_path = resolve_face_reference(profile_id)
    reference_frame = read_static_image(str(profile_path))
    output_frame = _decode_bgr(payload)
    reference_face = get_one_face(get_static_faces([reference_frame]))
    output_face = get_one_face(get_static_faces([output_frame]))
    if reference_face is None or output_face is None:
        raise RuntimeError("face evaluator could not detect both reference and output faces")

    reference_embedding = np.asarray(reference_face.embedding_norm, dtype=np.float32)
    output_embedding = np.asarray(output_face.embedding_norm, dtype=np.float32)
    denominator = float(
        np.linalg.norm(reference_embedding) * np.linalg.norm(output_embedding)
    )
    cosine = (
        float(np.dot(reference_embedding, output_embedding) / denominator)
        if denominator > 0
        else -1.0
    )
    identity = _clamp_score((cosine + 1.0) / 2.0)

    detector_score = float(output_face.score_set.get("detector") or 0.0)
    x1, y1, x2, y2 = [int(round(float(value))) for value in output_face.bounding_box]
    height, width = output_frame.shape[:2]
    x1, x2 = max(0, x1), min(width, x2)
    y1, y2 = max(0, y1), min(height, y2)
    crop = output_frame[y1:y2, x1:x2]
    if crop.size:
        low, high = np.percentile(crop, [5, 95])
        dynamic_range = _clamp_score(float(high - low) / 180.0)
        saturated = float(np.mean((crop <= 2) | (crop >= 253)))
    else:
        dynamic_range, saturated = 0.0, 1.0
    blend_proxy = _clamp_score(
        0.65 * _clamp_score(detector_score)
        + 0.35 * dynamic_range
        - min(0.25, saturated)
    )
    return identity, blend_proxy, output_embedding


async def evaluate_face(
    output_payload: bytes,
    profile_id: str,
    *,
    source_payload: bytes,
    media_metadata: dict[str, object],
    processing_ms: float,
):
    del source_payload
    if _FACE_WINDOW < 2:
        raise RuntimeError("face quality window must contain at least two frames")
    width = media_metadata.get("width")
    height = media_metadata.get("height")
    fps = media_metadata.get("fps")
    if (
        type(width) is not int
        or type(height) is not int
        or type(fps) not in (int, float)
        or not math.isfinite(float(fps))
    ):
        raise ValueError("face evaluator requires width, height, and fps metadata")

    session_id = _require_session_id(media_metadata)
    identity, blend, embedding = _face_measurements(output_payload, profile_id)
    state = _face_window_state(session_id, profile_id)
    temporal = 1.0
    if state.previous_embedding is not None:
        import numpy as np

        previous = np.asarray(state.previous_embedding, dtype=np.float32)
        current = np.asarray(embedding, dtype=np.float32)
        denominator = float(np.linalg.norm(previous) * np.linalg.norm(current))
        cosine = float(np.dot(previous, current) / denominator) if denominator > 0 else -1.0
        temporal = _clamp_score((cosine + 1.0) / 2.0)
    state.previous_embedding = embedding
    state.identities.append(identity)
    state.temporal.append(temporal)
    state.blend.append(blend)
    state.latencies.append(max(float(processing_ms), 0.001))

    observed = len(state.identities)
    if observed < _FACE_WINDOW:
        return FaceRealismWarmupEvidence(
            evaluator_id="seldrune-facefusion-final-frame-v1",
            evaluator_version="1.0",
            window_frames=observed,
            required_window_frames=_FACE_WINDOW,
            output_width=width,
            output_height=height,
            output_fps=float(fps),
        )
    return FaceRealismEvidence(
        evaluator_id="seldrune-facefusion-final-frame-v1",
        evaluator_version="1.0",
        window_frames=observed,
        output_width=width,
        output_height=height,
        output_fps=float(fps),
        identity_similarity=sum(state.identities) / observed,
        temporal_consistency=sum(state.temporal) / len(state.temporal),
        blend_quality=sum(state.blend) / len(state.blend),
        p95_inference_ms=_percentile95(state.latencies),
    )


def _pcm16(payload: bytes) -> list[float]:
    if not payload or len(payload) % 2:
        raise ValueError("voice evaluator requires signed 16-bit PCM")
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    return [float(value) / 32768.0 for value in samples]


def _voice_chunk(
    source_payload: bytes,
    output_payload: bytes,
    *,
    channels: int,
    processing_ms: float,
) -> _VoiceChunk:
    source = _pcm16(source_payload)
    output = _pcm16(output_payload)
    if len(source) != len(output) or len(source) % channels:
        raise ValueError("voice transform must preserve PCM sample count")

    source_power = sum(value * value for value in source)
    output_power = sum(value * value for value in output)
    dot = sum(a * b for a, b in zip(source, output, strict=True))
    if source_power > 1e-12 and output_power > 1e-12:
        correlation = dot / math.sqrt(source_power * output_power)
    else:
        correlation = 1.0 if source_power <= 1e-12 and output_power <= 1e-12 else 0.0
    speaker_preservation = _clamp_score(correlation)

    error_power = sum((a - b) ** 2 for a, b in zip(source, output, strict=True))
    content_preservation = _clamp_score(
        1.0 - error_power / max(source_power, 1e-9)
    )
    clipped = sum(abs(value) >= 0.995 for value in output) / max(len(output), 1)
    dropout = sum(
        abs(a) >= 0.01 and abs(b) < 0.0005 for a, b in zip(source, output, strict=True)
    ) / max(len(output), 1)
    rms_in = math.sqrt(source_power / max(len(source), 1))
    rms_out = math.sqrt(output_power / max(len(output), 1))
    level_delta = abs(rms_out - rms_in) / max(rms_in, 0.01)
    naturalness = _clamp_score(
        1.0 - min(1.0, clipped * 12.0 + dropout * 8.0 + level_delta * 0.15)
    )
    return _VoiceChunk(
        sample_count=len(output) // channels,
        speaker_preservation=speaker_preservation,
        content_preservation=content_preservation,
        naturalness=naturalness,
        clipped_fraction=clipped,
        dropout_fraction=dropout,
        processing_ms=max(float(processing_ms), 0.001),
    )


def _weighted_average(chunks: deque[_VoiceChunk], field_name: str) -> float:
    total = sum(chunk.sample_count for chunk in chunks)
    if total <= 0:
        return 0.0
    return sum(
        getattr(chunk, field_name) * chunk.sample_count for chunk in chunks
    ) / total


async def evaluate_voice(
    output_payload: bytes,
    profile_id: str,
    *,
    source_payload: bytes,
    media_metadata: dict[str, object],
    processing_ms: float,
):
    sample_rate = media_metadata.get("sample_rate_hz")
    channels = media_metadata.get("channels")
    if type(sample_rate) is not int or sample_rate != 48000:
        raise ValueError("voice evaluator requires 48 kHz PCM")
    if type(channels) is not int or channels not in (1, 2):
        raise ValueError("voice evaluator requires mono or stereo PCM")
    if not 0.1 <= _VOICE_WINDOW_SECONDS <= 5.0:
        raise RuntimeError("voice quality window is outside the supported range")

    session_id = _require_session_id(media_metadata)
    chunk = _voice_chunk(
        source_payload,
        output_payload,
        channels=channels,
        processing_ms=processing_ms,
    )
    state = _voice_window_state(session_id, profile_id, sample_rate, channels)
    state.chunks.append(chunk)
    state.total_samples += chunk.sample_count
    required_samples = max(1, int(round(sample_rate * _VOICE_WINDOW_SECONDS)))
    while (
        len(state.chunks) > 1
        and state.total_samples - state.chunks[0].sample_count >= required_samples
    ):
        removed = state.chunks.popleft()
        state.total_samples -= removed.sample_count

    observed_seconds = state.total_samples / sample_rate
    if observed_seconds + 1e-9 < _VOICE_WINDOW_SECONDS:
        return VoiceRealismWarmupEvidence(
            evaluator_id="seldrune-same-speaker-signal-integrity-v1",
            evaluator_version="1.0",
            window_duration_seconds=max(observed_seconds, 0.001),
            required_window_duration_seconds=_VOICE_WINDOW_SECONDS,
            sample_rate_hz=sample_rate,
            channels=channels,
        )

    latency_values = deque(
        (item.processing_ms for item in state.chunks),
        maxlen=len(state.chunks) or 1,
    )
    return VoiceRealismEvidence(
        evaluator_id="seldrune-same-speaker-signal-integrity-v1",
        evaluator_version="1.0",
        window_duration_seconds=observed_seconds,
        sample_rate_hz=sample_rate,
        channels=channels,
        speaker_similarity=_weighted_average(
            state.chunks, "speaker_preservation"
        ),
        content_preservation=_weighted_average(
            state.chunks, "content_preservation"
        ),
        naturalness=_weighted_average(state.chunks, "naturalness"),
        clipped_fraction=_weighted_average(state.chunks, "clipped_fraction"),
        dropout_fraction=_weighted_average(state.chunks, "dropout_fraction"),
        p95_processing_ms=_percentile95(latency_values),
    )
