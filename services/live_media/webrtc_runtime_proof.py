"""Local aiortc return-frame proof for LiveShift."""

from __future__ import annotations

import argparse
import asyncio
import json
from fractions import Fraction
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

    client = RTCPeerConnection()
    server = RTCPeerConnection()
    returned = asyncio.get_running_loop().create_future()

    source_track = SourceTrack()
    client.addTrack(source_track)

    @server.on("track")
    def on_server_track(track):
        if track.kind == "video":
            attach_reference_face_track(
                server,
                track,
                session,
                face_profile_id=args.profile_id,
                reference_provider=lambda _: reference,
            )

    @client.on("track")
    def on_client_track(track):
        if track.kind == "video" and not returned.done():
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
        await client.close()
        await server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--profile-id", default="authorized-webrtc-proof")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    print(json.dumps(asyncio.run(run_proof(parser.parse_args())), indent=2))


if __name__ == "__main__":
    main()
