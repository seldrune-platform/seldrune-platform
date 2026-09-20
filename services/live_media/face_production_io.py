"""Durable loading and cryptographic binding for Face production evidence."""

from __future__ import annotations

import json
from pathlib import Path

from services.live_media.face_production_gate import (
    FaceProductionEvidence,
    FaceProductionGates,
    evaluate_production_gates,
)
from services.live_media.face_training_executor import sha256_file
from services.live_media.face_verification_io import load_verification_receipt


def load_production_gates(
    evidence_path: str | Path,
    verification_receipt_path: str | Path,
) -> FaceProductionGates:
    """Validate both evidence files and return the resulting product gates."""
    evidence_payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    if not isinstance(evidence_payload, dict):
        raise ValueError("production evidence must be a JSON object")
    try:
        evidence = FaceProductionEvidence(**evidence_payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid production evidence schema") from exc

    receipt_path = Path(verification_receipt_path)
    load_verification_receipt(receipt_path)
    if sha256_file(receipt_path) != evidence.verification_receipt_sha256:
        raise ValueError("production evidence does not match the verification receipt")
    return evaluate_production_gates(evidence)
