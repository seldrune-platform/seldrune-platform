from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol


class VideoSink(Protocol):
    def open(self) -> object: ...
    async def send(self, frame: object) -> None: ...
    def close(self) -> None: ...


class AudioSink(Protocol):
    @property
    def connected(self) -> bool: ...
    def open(self) -> object: ...
    async def send(self, chunk: bytes) -> None: ...
    async def close(self) -> None: ...


@dataclass(frozen=True)
class DesktopCallReceipt:
    authorization_verified: bool
    disclosure_enabled: bool
    virtual_camera_connected: bool
    virtual_microphone_connected: bool
    video_frames: int
    audio_chunks: int
    video_width: int
    video_height: int
    audio_sample_rate_hz: int
    audio_channels: int

    @property
    def verified(self) -> bool:
        return (
            self.authorization_verified and self.disclosure_enabled
            and self.virtual_camera_connected and self.virtual_microphone_connected
            and self.video_frames > 0 and self.audio_chunks > 0
        )

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.update(state="succeeded" if self.verified else "failed",
                    desktop_call_output_verified=self.verified)
        return data


class SyntheticMediaBadge:
    """Burn a compact, unbranded AI-modified disclosure into outgoing RGB video."""

    def __call__(self, frame: bytes, width: int, height: int) -> object:
        try:
            import numpy as np
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise RuntimeError("NumPy and Pillow are required for disclosure") from exc
        expected = width * height * 3
        if width < 1 or height < 1 or len(frame) != expected:
            raise ValueError(f"invalid RGB24 frame; expected {expected} bytes")
        pixels = np.frombuffer(frame, dtype=np.uint8).reshape(height, width, 3)
        image = Image.fromarray(pixels).copy()
        draw = ImageDraw.Draw(image)
        size = max(12, min(16, height // 60))
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", size=size)
        except OSError:
            try:
                font = ImageFont.load_default(size=size)
            except TypeError:
                font = ImageFont.load_default()
        label = "AI modified"
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        pad_x, pad_y = max(6, size // 2), max(4, size // 3)
        inset = max(8, width // 100)
        x1 = max(0, width - (right - left) - 2 * pad_x - inset)
        y1 = max(0, height // 100)
        x2, y2 = min(width - 1, x1 + right - left + 2 * pad_x), min(
            height - 1, y1 + bottom - top + 2 * pad_y
        )
        draw.rounded_rectangle((x1, y1, x2, y2), radius=max(4, size // 3),
                               fill=(32, 38, 46), outline=(105, 112, 120), width=1)
        draw.text((x1 + pad_x - left, y1 + pad_y - top), label,
                  fill=(232, 235, 238), font=font)
        return np.asarray(image, dtype=np.uint8).copy()


class SoundDeviceVirtualMicrophoneSink:
    """Write PCM16 audio to a specifically named virtual-cable output device."""

    def __init__(self, device_name: str, *, sample_rate_hz: int = 48_000,
                 channels: int = 1) -> None:
        if not device_name.strip():
            raise ValueError("select a virtual microphone playback device")
        if sample_rate_hz < 8_000 or channels not in (1, 2):
            raise ValueError("unsupported audio format")
        self.device_name, self.sample_rate_hz, self.channels = (
            device_name, sample_rate_hz, channels
        )
        self._stream: object | None = None

    @property
    def connected(self) -> bool:
        return self._stream is not None

    def open(self) -> SoundDeviceVirtualMicrophoneSink:
        if self._stream is not None:
            raise RuntimeError("virtual microphone is already open")
        try:
            import sounddevice
        except ImportError as exc:
            raise RuntimeError("install sounddevice for microphone output") from exc
        matches = [
            i for i, d in enumerate(sounddevice.query_devices())
            if d["name"] == self.device_name
            and int(d["max_output_channels"]) >= self.channels
        ]
        if len(matches) != 1:
            reason = "not found" if not matches else "ambiguous"
            raise RuntimeError(f"virtual microphone device {reason}: {self.device_name}")
        stream = sounddevice.RawOutputStream(
            samplerate=self.sample_rate_hz, channels=self.channels, dtype="int16",
            device=matches[0], blocksize=0,
        )
        stream.start()
        self._stream = stream
        return self

    async def send(self, chunk: bytes) -> None:
        if self._stream is None:
            raise RuntimeError("virtual microphone is not open")
        unit = self.channels * 2
        if not chunk or len(chunk) % unit:
            raise ValueError(f"PCM16 chunk length must be a nonzero multiple of {unit}")
        await asyncio.to_thread(self._stream.write, bytes(chunk))

    async def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        def stop_and_close() -> None:
            try:
                stream.stop()
            finally:
                stream.close()
        await asyncio.to_thread(stop_and_close)


class DesktopLiveCallOutput:
    """Expose authorized, disclosed returned media as selectable OS devices."""

    def __init__(self, *, camera_sink: VideoSink, microphone_sink: AudioSink,
                 face_profile_id: str, voice_profile_id: str,
                 authorization_check: Callable[[str, str], bool],
                 width: int = 1280, height: int = 720,
                 sample_rate_hz: int = 48_000, audio_channels: int = 1,
                 disclosure_enabled: bool = True) -> None:
        if not face_profile_id or not voice_profile_id:
            raise ValueError("authorized face and voice profiles are required")
        if width < 1 or height < 1 or sample_rate_hz < 8_000 or audio_channels not in (1, 2):
            raise ValueError("invalid output format")
        self.camera, self.microphone = camera_sink, microphone_sink
        self.face_id, self.voice_id = face_profile_id, voice_profile_id
        self.authorize = authorization_check
        self.width, self.height = width, height
        self.sample_rate_hz, self.channels = sample_rate_hz, audio_channels
        self.disclosure_enabled = disclosure_enabled
        self.badge = SyntheticMediaBadge()
        self.started = self.authorized = False
        self.video_frames = self.audio_chunks = 0
        self.last_video_ms = self.last_audio_ms = -1

    def start(self) -> DesktopLiveCallOutput:
        if self.started:
            raise RuntimeError("output already started")
        if not self.disclosure_enabled:
            raise ValueError("visible synthetic-media disclosure must stay enabled")
        if self.authorize(self.face_id, self.voice_id) is not True:
            raise PermissionError("face and voice profile authorization is required")
        opened = self.camera.open()
        if opened is not None:
            self.camera = opened
        try:
            opened = self.microphone.open()
            if opened is not None:
                self.microphone = opened
        except Exception:
            self.camera.close()
            raise
        self.started = self.authorized = True
        return self

    async def publish_video(self, frame: bytes, timestamp_ms: int) -> None:
        if not self.started:
            raise RuntimeError("output is not started")
        if timestamp_ms < 0 or timestamp_ms < self.last_video_ms:
            raise ValueError("video timestamps must be nonnegative and monotonic")
        if len(frame) != self.width * self.height * 3:
            raise ValueError("video must be raw RGB24 at the configured dimensions")
        await self.camera.send(self.badge(frame, self.width, self.height))
        self.last_video_ms = timestamp_ms
        self.video_frames += 1

    async def publish_audio(self, chunk: bytes, timestamp_ms: int) -> None:
        if not self.started:
            raise RuntimeError("output is not started")
        if timestamp_ms < 0 or timestamp_ms < self.last_audio_ms:
            raise ValueError("audio timestamps must be nonnegative and monotonic")
        unit = self.channels * 2
        if not chunk or len(chunk) % unit:
            raise ValueError(f"PCM16 chunk length must be a nonzero multiple of {unit}")
        await self.microphone.send(chunk)
        self.last_audio_ms = timestamp_ms
        self.audio_chunks += 1

    @property
    def receipt(self) -> DesktopCallReceipt:
        return DesktopCallReceipt(
            self.authorized, self.disclosure_enabled,
            bool(getattr(self.camera, "connected", self.started)),
            bool(getattr(self.microphone, "connected", self.started)),
            self.video_frames, self.audio_chunks, self.width, self.height,
            self.sample_rate_hz, self.channels,
        )

    async def close(self) -> DesktopCallReceipt:
        delivered_receipt = self.receipt
        try:
            await self.microphone.close()
        finally:
            self.camera.close()
            self.started = False
        return delivered_receipt


def create_desktop_live_call_output(*, virtual_microphone_device: str,
                                    face_profile_id: str, voice_profile_id: str,
                                    authorization_check: Callable[[str, str], bool],
                                    width: int = 1280, height: int = 720,
                                    fps: int = 30, sample_rate_hz: int = 48_000,
                                    audio_channels: int = 1) -> DesktopLiveCallOutput:
    """Construct optional device adapters; OS drivers are separate installs."""
    from services.live_media.pyvirtualcam_adapter import PyVirtualCameraSink
    return DesktopLiveCallOutput(
        camera_sink=PyVirtualCameraSink(width=width, height=height, fps=fps),
        microphone_sink=SoundDeviceVirtualMicrophoneSink(
            virtual_microphone_device, sample_rate_hz=sample_rate_hz,
            channels=audio_channels,
        ),
        face_profile_id=face_profile_id, voice_profile_id=voice_profile_id,
        authorization_check=authorization_check, width=width, height=height,
        sample_rate_hz=sample_rate_hz, audio_channels=audio_channels,
    )



async def relay_returned_track(track: object, output: DesktopLiveCallOutput) -> None:
    """Relay one returned aiortc track to the selected OS devices until it ends."""
    import numpy as np

    kind = getattr(track, "kind", None)
    if kind not in ("video", "audio"):
        raise ValueError("returned track must be audio or video")
    while True:
        try:
            frame = await track.recv()
        except StopAsyncIteration:
            return
        pts, time_base = getattr(frame, "pts", None), getattr(frame, "time_base", None)
        if pts is None or time_base is None:
            raise ValueError("returned media frame must include pts and time_base")
        timestamp_ms = round(float(pts * time_base) * 1000)
        if kind == "video":
            pixels = frame.to_ndarray(format="rgb24")
            expected_shape = (output.height, output.width, 3)
            if tuple(pixels.shape) != expected_shape:
                raise ValueError(
                    f"returned video must have shape {expected_shape}, got {tuple(pixels.shape)}"
                )
            await output.publish_video(pixels.tobytes(), timestamp_ms)
            continue

        sample_rate = getattr(frame, "sample_rate", None)
        layout = getattr(frame, "layout", None)
        channels = len(getattr(layout, "channels", ()))
        if sample_rate != output.sample_rate_hz or channels != output.channels:
            raise ValueError("returned audio format does not match the selected output")
        samples = np.asarray(frame.to_ndarray(format="s16"), dtype=np.int16)
        if not samples.size:
            raise ValueError("returned audio frame is empty")
        await output.publish_audio(samples.tobytes(), timestamp_ms)
