"""Aetherion experimental runtime evidence API."""

from fastapi import APIRouter

from services.aetherion.evidence_api import build_evidence_payload
from services.aetherion.qir import QIROp, QIROpcode, QIRProgram

router = APIRouter(prefix="/aetherion", tags=["aetherion"])


def _probe_program() -> QIRProgram:
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=2),
            QIROp("b", QIROpcode.CONST, value=3),
            QIROp("out", QIROpcode.ADD, ("a", "b")),
        ),
        "out",
    )


@router.get("/evidence")
def evidence() -> dict[str, object]:
    return build_evidence_payload(_probe_program())
