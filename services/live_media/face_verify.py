"""Command-line verifier for Seldrune Face transformed-frame receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.live_media.face_verification_io import load_verification_receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Seldrune Face output evidence")
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def verify_receipt_file(path: str | Path) -> dict[str, object]:
    receipt = load_verification_receipt(path)
    return {
        "status": "verified",
        "run_id": receipt.run_id,
        "model_version": receipt.output.model_version,
        "checkpoint_sha256": receipt.output.checkpoint_sha256,
        "onnx_sha256": receipt.output.onnx_sha256,
        "frames_processed": receipt.stream.frames_processed,
        "frames_transformed": receipt.stream.frames_transformed,
        "identity_similarity": receipt.identity_similarity,
        "inference_ms": receipt.inference.inference_ms,
    }


def main() -> int:
    args = build_parser().parse_args()
    print(json.dumps(verify_receipt_file(args.receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
