"""Local aiortc return-frame proof for LiveShift.

This proof uses two in-process RTCPeerConnections so signaling and media cross
a real WebRTC peer boundary before the returned video frame is accepted.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path


async def run_proof(args: argparse.Namespace) -> dict[str, object]:
    try:
        import numpy as np
        from av import VideoFrame
        from aiortc import MediaStreamTrack, RTCPeerConnection
    except ImportError as exc:
        raise RuntimeError("aiortc, PyAV, and NumPy are required") from exc

    from .face_onnx_loader import load_face_onnx
    from .reference_runtime import attach_reference_face_track
    from .gpu_runtime_proof import _load_tensor

    session, loaded = load_face_onnx(
        args.model, expected_sha256=args.sha256, prefer_cuda=True
    )
    if not loaded.providers or loaded.providers[0] != "CUDAExecutionProvider":
        raise RuntimeError("CUDAExecutionProvider must be active")

    reference = _load_tensor(Path(args.reference))
    source = _load_tensor(Path(args.source))

    class SourceTrack(MediaStreamTrack):
        kind = "video"

        async def recv(self):
            rgb = np.transpose(source[0], (1, 2, 0))
            rgb = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
            frame = VideoFrame.from_ndarray(rgb, format="rgb24")
            frame.pts = 0
            frame.time_base = __import__("fractions").Fraction(1, 30)
            return frame

    sender = RTCPeerConnection()
    receiver = RTCPeerConnection()
    returned = asyncio.get_running_loop().create_future()

    @receiver.on("track")
    def on_track(track):
        if track.kind == "video" and not returned.done():
            async def receive_one():
                returned.set_result(await track.recv())
            asyncio.create_task(receive_one())

    source_track = SourceTrack()
    attach_reference_face_track(
        sender,
        source_track,
        session,
        face_profile_id=args.profile_id,
        reference_provider=lambda _: reference,
    )

    offer = await sender.createOffer()
    await sender.setLocalDescription(offer)
    await receiver.setRemoteDescription(sender.localDescription)
    answer = await receiver.createAnswer()
    await receiver.setLocalDescription(answer)
    await sender.setRemoteDescription(receiver.localDescription)

    try:
        frame = await asyncio.wait_for(returned, timeout=args.timeout)
        array = frame.to_ndarray(format="rgb24")
        valid = array.shape == (256, 256, 3) and np.isfinite(array).all()
        if not valid:
            raise RuntimeError("returned WebRTC frame is invalid")
        receipt = {
            "state": "succeeded",
            "webrtc_peer_returned": True,
            "cuda_provider_active": True,
            "providers": list(loaded.providers),
            "returned_shape": list(array.shape),
            "returned_finite": True,
        }
        Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
    finally:
        await sender.close()
        await receiver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--profile-id", default="authorized-webrtc-proof")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    print(json.dumps(asyncio.run(run_proof(parser.parse_args())), indent=2))


if __name__ == "__main__":
    main()
