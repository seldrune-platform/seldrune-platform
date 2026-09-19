from services.aetherion.evidence_api import build_evidence_payload
from services.aetherion.evidence_history import EvidenceHistory
from services.aetherion.qir import QIROp, QIROpcode, QIRProgram


def sample_program():
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=3),
            QIROp("b", QIROpcode.CONST, value=9),
            QIROp("out", QIROpcode.MUL, ("a", "b")),
        ),
        "out",
    )


def test_observability_payload_keeps_physical_qgpu_unverified():
    payload = build_evidence_payload(sample_program())
    assert payload["health"]["software_ready"]
    assert payload["health"]["research_status"] == "experimental"
    assert payload["health"]["physical_qgpu_status"] == "unverified"
    assert not payload["runtime"]["quantum_speedup_verified"]


def test_evidence_history_is_bounded():
    history = EvidenceHistory(limit=2)
    history.append({"run": 1})
    history.append({"run": 2})
    history.append({"run": 3})
    assert history.items() == ({"run": 2}, {"run": 3})
    assert history.latest() == {"run": 3}
