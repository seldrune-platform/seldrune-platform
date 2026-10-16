"""Consent-gated streaming adapter for the pretrained Seed-VC runtime.

The upstream implementation is installed separately under SEEDVC_HOME.
This module only loads it after a signed Seldrune session has prepared an
approved profile. It performs inference only; it never fine-tunes a model.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import math
import os
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

from .live_profile_store import resolve_voice_reference

import numpy as np

MODEL_REPO = "Plachta/Seed-VC"
MODEL_REVISION = "609dd03a0312184629d90659f56d72b3132fb696"
MODEL_CONFIG_REVISION = "5cffe4f001043a09d6e871e43cdcdb7aa75b7e8c"
MODEL_CHECKPOINT = "DiT_uvit_tat_xlsr_ema.pth"
MODEL_CONFIG = "config_dit_mel_seed_uvit_xlsr_tiny.yml"
MODEL_CHECKPOINT_SHA256 = "c853ea578b409f625f961bcb15d5cff1f8ef9a75f3209ec21d9b7c73ab422e88"

_SAMPLE_RATE = 48_000
_MODEL_RATE = 22_050
_BLOCK_20MS_FRAMES = 12
_BLOCK_SAMPLES_48K = _SAMPLE_RATE * 240 // 1000
_LEFT_CONTEXT_SECONDS = 2.5
_RIGHT_CONTEXT_SECONDS = 0.02
_CROSSFADE_SECONDS = 0.04
_SEARCH_SECONDS = 0.02
_MAX_PROFILES = 8
_MAX_STREAMS = 8
_STATE_TTL_SECONDS = 600.0


class ConversionEngine(Protocol):
    def prepare(self, profile_id: str, reference_path: Path) -> np.ndarray: ...

    def convert_block(
        self, reference_path: Path, reference_audio: np.ndarray, state: _StreamState,
        source_block_48k: np.ndarray,
    ) -> np.ndarray: ...


@dataclass
class _Reference:
    path: Path
    audio: np.ndarray
    sha256: str
    last_used: float = field(default_factory=time.monotonic)


@dataclass
class _StreamState:
    profile_id: str
    channels: int
    pending_48k: np.ndarray
    output_48k: np.ndarray
    model_context: np.ndarray
    overlap_tail: np.ndarray
    last_sequence: int | None = None
    last_used: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class _SeedVCRealtimeEngine:
    """Load the upstream real-time model once and keep it resident on CUDA."""

    def __init__(self) -> None:
        self._module = None
        self._model_set = None
        self._torch = None
        self._librosa = None
        self._device = None
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._model_set is not None:
            return
        import torch
        import librosa
        from huggingface_hub import hf_hub_download

        if not torch.cuda.is_available():
            raise RuntimeError("Seed-VC runtime requires a CUDA GPU")
        repo = Path(os.getenv("SEEDVC_HOME", "/opt/seed-vc")).resolve()
        source = repo / "real-time-gui.py"
        if not source.is_file():
            raise RuntimeError("Seed-VC source is missing at SEEDVC_HOME")
        sys.path.insert(0, str(repo))
        spec = importlib.util.spec_from_file_location(
            "seldrune_seedvc_realtime", source
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Seed-VC real-time module could not be loaded")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        cache = os.getenv("HF_HOME")

        def cached_model_download(
            repo_id, model_filename="pytorch_model.bin", config_filename=None
        ):
            model_path = hf_hub_download(
                repo_id=repo_id,
                filename=model_filename,
                cache_dir=cache,
            )
            if config_filename is None:
                return model_path
            config_path = hf_hub_download(
                repo_id=repo_id,
                filename=config_filename,
                cache_dir=cache,
            )
            return model_path, config_path

        module.load_custom_model_from_hf = cached_model_download
        checkpoint = Path(
            hf_hub_download(
                repo_id=MODEL_REPO, filename=MODEL_CHECKPOINT,
                revision=MODEL_REVISION, cache_dir=cache,
            )
        )
        actual_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if actual_hash != MODEL_CHECKPOINT_SHA256:
            raise RuntimeError("Seed-VC checkpoint hash does not match the pinned model")
        config = hf_hub_download(
            repo_id=MODEL_REPO, filename=MODEL_CONFIG,
            revision=MODEL_CONFIG_REVISION, cache_dir=cache,
        )
        device = torch.device("cuda")
        module.device = device
        model_set = module.load_models(
            SimpleNamespace(
                fp16=True,
                checkpoint_path=str(checkpoint),
                config_path=str(config),
            )
        )
        if model_set[-1].get("sampling_rate") != _MODEL_RATE:
            raise RuntimeError("Seed-VC checkpoint has an unexpected sample rate")
        self._module = module
        self._model_set = model_set
        self._torch = torch
        self._librosa = librosa
        self._device = device

    def prepare(self, profile_id: str, reference_path: Path) -> np.ndarray:
        del profile_id
        with self._lock:
            self._load()
            assert self._librosa is not None
            import soundfile as sf

            duration = float(sf.info(str(reference_path)).duration)
            if duration < 1.0 or duration > 30.0:
                raise ValueError("voice reference must be 1 to 30 seconds")
            audio, _ = self._librosa.load(
                str(reference_path), sr=_MODEL_RATE, mono=True
            )
        audio = np.asarray(audio, dtype=np.float32)
        if audio.size < _MODEL_RATE or audio.size > _MODEL_RATE * 30:
            raise ValueError("voice reference must be 1 to 30 seconds")
        if not np.isfinite(audio).all() or float(np.max(np.abs(audio))) < 1e-4:
            raise ValueError("voice reference must contain finite audible speech")
        return audio

    def convert_block(
        self, reference_path: Path, reference_audio: np.ndarray,
        state: _StreamState, source_block_48k: np.ndarray,
    ) -> np.ndarray:
        from scipy.signal import resample_poly

        with self._lock:
            self._load()
            assert self._librosa is not None
            assert self._torch is not None
            assert self._module is not None
            assert self._model_set is not None
            module = self._module
            torch = self._torch
            sample_rate = _MODEL_RATE
            zc = sample_rate // 50
            block_samples = _BLOCK_20MS_FRAMES * zc
            crossfade_samples = int(_CROSSFADE_SECONDS * sample_rate)
            search_samples = int(_SEARCH_SECONDS * sample_rate)
            left_context = int(_LEFT_CONTEXT_SECONDS * sample_rate)
            right_context = int(_RIGHT_CONTEXT_SECONDS * sample_rate)

            source_block = resample_poly(source_block_48k, 147, 320).astype(
                np.float32, copy=False
            )
            if source_block.size != block_samples:
                raise RuntimeError("Seed-VC input block has an unexpected duration")
            context = state.model_context
            context[:-block_samples] = context[block_samples:]
            context[-block_samples:] = source_block
            source_16k = resample_poly(context, 320, 441).astype(
                np.float32, copy=False
            )
            expected_16k = 320 * context.size // zc
            source_16k = source_16k[:expected_16k]
            source_tensor = torch.from_numpy(source_16k).to(self._device)

            block_frame_16k = 320 * _BLOCK_20MS_FRAMES
            skip_head = left_context // zc
            skip_tail = right_context // zc
            return_length = (
                block_samples + crossfade_samples + search_samples
            ) // zc
            output = module.custom_infer(
                self._model_set,
                reference_audio,
                str(reference_path),
                source_tensor,
                block_frame_16k,
                skip_head,
                skip_tail,
                return_length,
                int(os.getenv("SEEDVC_DIFFUSION_STEPS", "6")),
                float(os.getenv("SEEDVC_INFERENCE_CFG_RATE", "0.7")),
                3.0,
                _LEFT_CONTEXT_SECONDS - 0.5,
            )
            converted = output.detach().float().cpu().numpy().reshape(-1)
            converted = self._align_output(
                converted, state, block_samples, crossfade_samples, search_samples
            )
            output_48k = resample_poly(converted, 320, 147).astype(
                np.float32, copy=False
            )
            if output_48k.size != _BLOCK_SAMPLES_48K:
                raise RuntimeError("Seed-VC output block changed its duration")
            return output_48k

    @staticmethod
    def _align_output(
        converted: np.ndarray, state: _StreamState, block_samples: int,
        crossfade_samples: int, search_samples: int,
    ) -> np.ndarray:
        required = block_samples + crossfade_samples
        if converted.size < required:
            converted = np.pad(converted, (0, required - converted.size))
        overlap = state.overlap_tail
        offset = 0
        if overlap.size and np.any(overlap):
            candidates = converted[: crossfade_samples + search_samples]
            scores = []
            for candidate_offset in range(search_samples + 1):
                segment = candidates[
                    candidate_offset : candidate_offset + crossfade_samples
                ]
                if segment.size != crossfade_samples:
                    scores.append(-math.inf)
                    continue
                denom = float(np.linalg.norm(segment) * np.linalg.norm(overlap))
                scores.append(
                    float(np.dot(segment, overlap) / denom) if denom > 1e-8 else 0.0
                )
            offset = int(np.argmax(scores))
        aligned = converted[offset:]
        if aligned.size < required:
            aligned = np.pad(aligned, (0, required - aligned.size))
        fade_in = np.sin(
            0.5 * np.pi * np.linspace(0.0, 1.0, crossfade_samples)
        ) ** 2
        fade_out = 1.0 - fade_in
        aligned[:crossfade_samples] = (
            aligned[:crossfade_samples] * fade_in + overlap * fade_out
        )
        state.overlap_tail = aligned[
            block_samples : block_samples + crossfade_samples
        ].copy()
        return aligned[:block_samples].copy()


class SeedVCVoiceAdapter:
    """Buffer live 48 kHz PCM into model blocks and preserve frame duration."""

    def __init__(self, engine: ConversionEngine | None = None) -> None:
        self._engine = engine or _SeedVCRealtimeEngine()
        self._references: OrderedDict[str, _Reference] = OrderedDict()
        self._states: OrderedDict[str, _StreamState] = OrderedDict()
        self._lock = asyncio.Lock()

    async def prepare_profile(self, profile_id: str) -> None:
        path, digest = resolve_voice_reference(profile_id)
        audio = await asyncio.to_thread(self._engine.prepare, profile_id, path)
        async with self._lock:
            self._prune_locked()
            self._references[profile_id] = _Reference(path, audio, digest)
            self._references.move_to_end(profile_id)
            while len(self._references) > _MAX_PROFILES:
                self._references.popitem(last=False)

    async def transform_voice(
        self, payload: bytes, profile_id: str, *,
        media_metadata: dict[str, object] | None = None,
    ) -> bytes:
        metadata = media_metadata or {}
        session_id = metadata.get("session_id")
        sample_rate = metadata.get("sample_rate_hz")
        channels = metadata.get("channels")
        sequence = metadata.get("sequence")
        if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
            raise ValueError("Seed-VC requires a live session id")
        if (
            type(sample_rate) is not int
            or sample_rate != _SAMPLE_RATE
            or type(channels) is not int
            or channels not in (1, 2)
        ):
            raise ValueError("Seed-VC requires 48 kHz mono or stereo PCM")
        if not isinstance(payload, bytes) or not payload or len(payload) % (2 * channels):
            raise ValueError("Seed-VC requires aligned signed 16-bit PCM")
        if sequence is not None and type(sequence) is not int:
            raise ValueError("Seed-VC sequence number must be an integer")

        async with self._lock:
            self._prune_locked()
            reference = self._references.get(profile_id)
            if reference is None:
                raise RuntimeError("voice profile must be prepared before conversion")
            reference.last_used = time.monotonic()
            state = self._states.get(session_id)
            if state is None or state.profile_id != profile_id or state.channels != channels:
                state = _new_state(profile_id, channels)
                self._states[session_id] = state
            if (
                sequence is not None
                and state.last_sequence is not None
                and sequence != state.last_sequence + 1
            ):
                state = _new_state(profile_id, channels)
                self._states[session_id] = state
            state.last_sequence = sequence
            state.last_used = time.monotonic()
            self._states.move_to_end(session_id)
            while len(self._states) > _MAX_STREAMS:
                self._states.popitem(last=False)

        async with state.lock:
            pcm = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
            pcm = pcm.reshape(-1, channels).mean(axis=1)
            state.pending_48k = np.concatenate((state.pending_48k, pcm))
            if state.pending_48k.size > _SAMPLE_RATE * 3:
                raise RuntimeError("Seed-VC input buffer exceeded its safety limit")
            while state.pending_48k.size >= _BLOCK_SAMPLES_48K:
                block = state.pending_48k[:_BLOCK_SAMPLES_48K]
                state.pending_48k = state.pending_48k[_BLOCK_SAMPLES_48K:]
                converted = await asyncio.to_thread(
                    self._engine.convert_block,
                    reference.path,
                    reference.audio,
                    state,
                    block.copy(),
                )
                state.output_48k = np.concatenate((state.output_48k, converted))
                if state.output_48k.size > _SAMPLE_RATE * 3:
                    raise RuntimeError("Seed-VC output buffer exceeded its safety limit")

            frame_samples = len(payload) // (2 * channels)
            if state.output_48k.size >= frame_samples:
                result = state.output_48k[:frame_samples]
                state.output_48k = state.output_48k[frame_samples:]
            else:
                result = np.zeros(frame_samples, dtype=np.float32)
                if state.output_48k.size:
                    available = state.output_48k.size
                    result[:available] = state.output_48k
                    state.output_48k = np.empty(0, dtype=np.float32)
            interleaved = np.repeat(result[:, None], channels, axis=1).reshape(-1)
            encoded = np.clip(interleaved * 32767.0, -32768, 32767).astype("<i2")
            return encoded.tobytes()

    def _prune_locked(self) -> None:
        cutoff = time.monotonic() - _STATE_TTL_SECONDS
        for profile_id, reference in list(self._references.items()):
            if reference.last_used < cutoff:
                del self._references[profile_id]
        for session_id, state in list(self._states.items()):
            if state.last_used < cutoff:
                del self._states[session_id]


def _new_state(profile_id: str, channels: int) -> _StreamState:
    sample_rate = _MODEL_RATE
    zc = sample_rate // 50
    block_samples = _BLOCK_20MS_FRAMES * zc
    crossfade_samples = int(_CROSSFADE_SECONDS * sample_rate)
    search_samples = int(_SEARCH_SECONDS * sample_rate)
    context_samples = (
        int(_LEFT_CONTEXT_SECONDS * sample_rate)
        + crossfade_samples
        + search_samples
        + block_samples
        + int(_RIGHT_CONTEXT_SECONDS * sample_rate)
    )
    return _StreamState(
        profile_id=profile_id,
        channels=channels,
        pending_48k=np.empty(0, dtype=np.float32),
        output_48k=np.empty(0, dtype=np.float32),
        model_context=np.zeros(context_samples, dtype=np.float32),
        overlap_tail=np.zeros(crossfade_samples, dtype=np.float32),
    )


_ADAPTER = SeedVCVoiceAdapter()


async def prepare_profile(profile_id: str) -> None:
    await _ADAPTER.prepare_profile(profile_id)


async def transform_voice(
    payload: bytes, profile_id: str, *,
    media_metadata: dict[str, object] | None = None,
) -> bytes:
    return await _ADAPTER.transform_voice(
        payload, profile_id, media_metadata=media_metadata
    )
