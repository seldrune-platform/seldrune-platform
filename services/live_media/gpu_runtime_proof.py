"""GPU runtime proof for the composed LiveShift Face v0.1 path."""

from __future__ import annotations

import argparse
import asyncio
import json
from hashlib import sha256
from pathlib import Path

from .face_onnx_loader import load_face_onnx
from .processors import MediaFrame
from .reference_runtime import build_reference_face_pipeline


def _load_tensor(path: Path):
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("NumPy and Pillow are required for runtime proof") from exc
    image = Image.open(path).convert("RGB").resize((256, 256))
    array = np.asarray(image, dtype=np.float32) / 255.0
    return np.transpose(array, (2, 0, 1))[None, ...]


async def run_proof(args: argparse.Namespace) -> dict[str, object]:
    session, loaded = load_face_onnx(
        args.model,
        expected_sha256=args.sha256,
        prefer_cuda=True,
    )
    if not loaded.providers or loaded.providers[0] != "CUDAExecutionProvider":
        raise RuntimeError("CUDAExecutionProvider must be active for GPU proof")

    reference = _load_tensor(Path(args.reference))
    source = _load_tensor(Path(args.source))
    pipeline = build_reference_face_pipeline(
        session,
        face_profile_id=args.profile_id,
        reference_provider=lambda _: reference,
    )
    result = await pipeline.video_frame(MediaFrame(source, 0))

    import numpy as np

    output = np.asarray(result.payload)
    if output.shape != (1, 3, 256, 256) or not np.isfinite(output).all():
        raise RuntimeError("Face v0.1 runtime returned invalid output")

    receipt = {
        "state": "succeeded",
        "model_sha256": loaded.sha256,
        "providers": list(loaded.providers),
        "input_names": list(loaded.input_names),
        "output_names": list(loaded.output_names),
        "output_shape": list(output.shape),
        "output_finite": True,
        "source_sha256": sha256(Path(args.source).read_bytes()).hexdigest(),
        "reference_sha256": sha256(Path(args.reference).read_bytes()).hexdigest(),
    }
    Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--profile-id", default="authorized-runtime-proof")
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_proof(args)), indent=2))


if __name__ == "__main__":
    main()
