"""End-to-end combined LiveShift A/V WebRTC runtime proof."""

from __future__ import annotations

import argparse
import asyncio
import json
from fractions import Fraction
from pathlib import Path


async def run_proof(args: argparse.Namespace) -> dict[str, object]:
    try:
        import numpy as np
        from aiortc import MediaStreamTrack, RTCPeerConnection
        from av import AudioFrame, VideoFrame
    except ImportError as exc:
        raise RuntimeError("aiortc, PyAV, and NumPy are required") from exc

    from .av_return_evidence import capture_av_return_evidence
    from .combined_av_runtime import (
        attach_reference_av_tracks,
        build_reference_av_pipeline,
    )
    from .face_onnx_loader import load_face_onnx
    from .gpu_runtime_proof import _load_tensor
    from .receiver_observation import ReceiverObservationRecorder

    session, loaded = load_face_onnx(
        args.model, expected_sha256=args.sha256, prefer_cuda=True
    )
    if not loaded.providers or loaded.providers[0] != "CUDAExecutionProvider":
        raise RuntimeError("CUDAExecutionProvider must be active")

    source = _load_tensor(Path(args.source))
    reference = _load_tensor(Path(args.reference))

    class VideoSource(MediaStreamTrack):
        kind = "video"

        def __init__(self) -> None:
            super().__init__()
            self._pts = 0

        async def recv(self):
            await asyncio.sleep(1 / 30)
            rgb = np.transpose(source[0], (1, 2, 0))
            rgb = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
            frame = VideoFrame.from_ndarray(rgb, format="rgb24")
            frame.pts = self._pts
            frame.time_base = Fraction(1, 90000)
            self._pts += 3000
            return frame

    class AudioSource(MediaStreamTrack):
        kind = "audio"

        def __init__(self) -> None:
            super().__init__()
            self._pts = 0

        async def recv(self):
            await asyncio.sleep(0.02)
            samples = np.zeros((1, 960), dtype=np.float32)
            samples[0, 0] = 0.25
            frame = AudioFrame.from_ndarray(
                samples, format="fltp", layout="mono"
            )
            frame.sample_rate = 48000
            frame.pts = self._pts
            frame.time_base = Fraction(1, 48000)
            self._pts += 960
            return frame

    async def voice_inference(speech, voice_reference):
        if voice_reference != b"authorized-reference":
            raise RuntimeError("unexpected voice reference")
        return np.asarray(speech, dtype=np.float32)

    pipeline = build_reference_av_pipeline(
        session,
        face_profile_id=args.face_profile_id,
        face_reference_provider=lambda _: reference,
        voice_profile_id=args.voice_profile_id,
        voice_reference_provider=lambda _: b"authorized-reference",
        voice_inference=voice_inference,
    )

    client = RTCPeerConnection()
    server = RTCPeerConnection()
    returned_video = asyncio.get_running_loop().create_future()
    returned_audio = asyncio.get_running_loop().create_future()
    server_tracks = {}
    receiver_observations = ReceiverObservationRecorder()

    client.addTrack(VideoSource())
    client.addTrack(AudioSource())

    @server.on("track")
    def on_server_track(track):
        server_tracks[track.kind] = track
        if "video" in server_tracks and "audio" in server_tracks:
            if not getattr(server, "_seldrune_av_attached", False):
                attach_reference_av_tracks(
                    server,
                    video_track=server_tracks["video"],
                    audio_track=server_tracks["audio"],
                    pipeline=pipeline,
                )
                server._seldrune_av_attached = True

    @client.on("track")
    def on_client_track(track):
        target = returned_video if track.kind == "video" else returned_audio
        if not target.done():

            async def receive_one():
                try:
                    frame = await track.recv()
                    if track.kind == "video":
                        receiver_observations.record_video(frame)
                    else:
                        receiver_observations.record_audio(frame)
                    target.set_result(frame)
                except Exception as exc:
                    if not target.done():
                        target.set_exception(exc)

            asyncio.create_task(receive_one())

    offer = await client.createOffer()
    await client.setLocalDescription(offer)
    await server.setRemoteDescription(client.localDescription)
    answer = await server.createAnswer()
    await server.setLocalDescription(answer)
    await client.setRemoteDescription(server.localDescription)

    try:
        video_frame, audio_frame = await asyncio.wait_for(
            asyncio.gather(returned_video, returned_audio),
            timeout=args.timeout,
        )
        video_observation = receiver_observations.latest_video
        audio_observation = receiver_observations.latest_audio
        if video_observation is None or audio_observation is None:
            raise RuntimeError("client receive observations are incomplete")
        video = video_frame.to_ndarray(format="rgb24")
        audio = audio_frame.to_ndarray()
        if video.shape != (256, 256, 3) or not np.isfinite(video).all():
            raise RuntimeError("returned video is invalid")
        if audio.size == 0 or not np.isfinite(audio).all():
            raise RuntimeError("returned audio is invalid")
        evidence = capture_av_return_evidence(
            pipeline, video_returned=True, audio_returned=True
        )
        receipt = evidence.as_receipt()
        receipt.update(
            {
                "cuda_provider_active": True,
                "providers": list(loaded.providers),
                "video_shape": list(video.shape),
                "audio_sample_rate": audio_frame.sample_rate,
                "client_received_video_frames": receiver_observations.video_frames,
                "client_received_audio_duration_seconds": (
                    receiver_observations.audio_duration_seconds
                ),
                "client_received_video": {
                    "width": video_observation.width,
                    "height": video_observation.height,
                    "timestamp_ms": video_observation.timestamp_ms,
                },
                "client_received_audio": {
                    "sample_rate_hz": audio_observation.sample_rate_hz,
                    "timestamp_ms": audio_observation.timestamp_ms,
                },
            }
        )
        if not evidence.verified:
            raise RuntimeError(
                f"combined A/V drift exceeded budget: {evidence.drift_ms} ms"
            )
        Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "
")
        return receipt
    finally:
        await client.close()
        await server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--face-profile-id", default="authorized-face-proof")
    parser.add_argument("--voice-profile-id", default="authorized-voice-proof")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    print(json.dumps(asyncio.run(run_proof(parser.parse_args())), indent=2))


if __name__ == "__main__":
    main()
