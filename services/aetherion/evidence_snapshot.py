"""Serializable Aetherion runtime evidence for APIs and consoles."""

from __future__ import annotations

from dataclasses import asdict

from .qir import QIRProgram
from .runtime_evidence import collect_runtime_evidence


def evidence_snapshot(program: QIRProgram) -> dict[str, object]:
    receipt = collect_runtime_evidence(program)
    data = asdict(receipt)
    data["evidence"] = receipt.evidence.value
    return data
