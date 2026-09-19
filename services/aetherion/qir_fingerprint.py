"""Stable fingerprints for Aetherion Q-IR research programs."""

from __future__ import annotations

import hashlib
import json

from .qir import QIRProgram


def program_fingerprint(program: QIRProgram) -> str:
    payload = [
        {
            "id": op.op_id,
            "opcode": op.opcode.value,
            "inputs": list(op.inputs),
            "value": op.value,
        }
        for op in program.operations
    ]
    encoded = json.dumps(
        {"operations": payload, "output": program.output_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
