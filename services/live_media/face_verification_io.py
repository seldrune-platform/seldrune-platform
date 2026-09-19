"""Durable JSON I/O for unified Seldrune Face verification receipts."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from services.live_media.face_inference_evidence import FaceInferenceEvidence
from services.live_media.face_output_manifest import FaceOutputManifest
from services.live_media.face_stream_gate import FaceStreamEvidence
from services.live_media.face_verification_receipt import FaceVerificationReceipt


def verification_receipt_payload(receipt: FaceVerificationReceipt) -> dict[str, Any]:
    receipt.validate()
    return asdict(receipt)


def write_verification_receipt(
    receipt: FaceVerificationReceipt,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = verification_receipt_payload(receipt)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target


def load_verification_receipt(path: str | Path) -> FaceVerificationReceipt:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("verification receipt must be a JSON object")
    try:
        output = FaceOutputManifest(**payload["output"])
        inference = FaceInferenceEvidence(**payload["inference"])
        stream = FaceStreamEvidence(**payload["stream"])
        receipt = FaceVerificationReceipt(
            run_id=payload["run_id"],
            output=output,
            inference=inference,
            stream=stream,
            reference_sha256=payload["reference_sha256"],
            identity_similarity=float(payload["identity_similarity"]),
            frame_change_ratio=float(payload["frame_change_ratio"]),
            authorization_verified=payload["authorization_verified"],
            synthetic_media_indicator_verified=payload[
                "synthetic_media_indicator_verified"
            ],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid verification receipt schema") from exc
    if not isinstance(receipt.authorization_verified, bool) or not isinstance(
        receipt.synthetic_media_indicator_verified, bool
    ):
        raise ValueError("verification flags must be booleans")
    receipt.validate()
    return receipt
