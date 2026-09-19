"""CLI proof for a real OS virtual-camera device.

Run this on the desktop/companion host, not the cloud GPU host. A successful
receipt means pyvirtualcam opened a real backend and accepted RGB frames.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .pyvirtualcam_adapter import PyVirtualCameraSink
from .virtual_camera_runtime_proof import prove_virtual_camera_delivery


def _load_rgb(path: Path, width: int, height: int) -> object:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow and NumPy are required for device proof") from exc
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB").resize((width, height)), dtype=np.uint8)


async def _run(args: argparse.Namespace) -> dict[str, object]:
    frame = _load_rgb(args.frame, args.width, args.height)
    sink = PyVirtualCameraSink(width=args.width, height=args.height, fps=args.fps)
    try:
        sink.open()
        last = None
        for _ in range(args.frames):
            last = await prove_virtual_camera_delivery(sink, frame)
        assert last is not None
        return {
            "state": last.state,
            "virtual_camera_connected": last.virtual_camera_connected,
            "frames_delivered": args.frames,
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
        }
    finally:
        sink.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()
    if args.frames < 1:
        raise SystemExit("--frames must be >= 1")
    receipt = asyncio.run(_run(args))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
