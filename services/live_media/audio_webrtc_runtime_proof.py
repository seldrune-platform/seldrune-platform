"""Local aiortc audio return proof for LiveShift voice transport."""

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
        from av import AudioFrame
    except ImportError as exc:
        raise RuntimeError("aiortc, PyAV, and NumPy are required") from exc

    from .pipeline import LivePipeline
    from .processors import PassthroughVideoProcessor
    from .reference_voice_runtime import (
        ReferenceVoiceProcessor,
        attach_reference_voice_track,
    )

    class SourceTrack(MediaStreamTrack):
        kind = "audio"

        def __init__(self) -> None:
            super().__init__()
            self._pts = 0

        async def recv(self):
            await asyncio.sleep(0.02)
            samples = np.zeros((1, 960), dtype=np.float32)
            samples[0, 0] = 0.25
            frame = AudioFrame.from_ndarray(samples, format="fltp", layout="mono")
            frame.sample_rate = 48000
            frame.pts = self._pts
            frame.time_base = Fraction(1, 48000)
            self._pts += 960
            return frame

    async def proof_inference(speech, reference):
        if reference != b"authorized-reference":
            raise RuntimeError("unexpected reference")
        return np.asarray(speech, dtype=np.float32)

    pipeline = LivePipeline(
        video=PassthroughVideoProcessor(),
        audio=ReferenceVoiceProcessor(
            reference_provider=lambda profile_id: b"authorized-reference",
            inference=proof_inference,
        ),
        voice_profile_id=args.profile_id,
    )

    client = RTCPeerConnection()
    server = RTCPeerConnection()
    returned = asyncio.get_running_loop().create_future()
    client.addTrack(SourceTrack())

    @server.on("track")
    def on_server_track(track):
        if track.kind == "audio":
            attach_reference_voice_track(server, track, pipeline)

    @client.on("track")
    def on_client_track(track):
        if track.kind == "audio" and not returned.done():

            async def receive_one():
                try:
                    returned.set_result(await track.recv())
                except Exception as exc:
                    if not returned.done():
                        returned.set_exception(exc)

            asyncio.create_task(receive_one())

    offer = await client.createOffer()
    await client.setLocalDescription(offer)
    await server.setRemoteDescription(client.localDescription)
    answer = await server.createAnswer()
    await server.setLocalDescription(answer)
    await client.setRemoteDescription(server.localDescription)

    try:
        frame = await asyncio.wait_for(returned, timeout=args.timeout)
        samples = frame.to_ndarray()
        valid = samples.size > 0 and np.isfinite(samples).all()
        if not valid:
            raise RuntimeError("returned WebRTC audio frame is invalid")
        receipt = {
            "state": "succeeded",
            "webrtc_audio_returned": True,
            "authorized_reference_used": True,
            "sample_rate": frame.sample_rate,
            "returned_finite": True,
        }
        Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
    finally:
        await client.close()
        await server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-id", default="authorized-voice-proof")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    print(json.dumps(asyncio.run(run_proof(parser.parse_args())), indent=2))


if __name__ == "__main__":
    main()
