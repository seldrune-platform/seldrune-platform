import pytest

from services.supreme.proof_mesh import ProofVerdict, evaluate_result
from services.supreme.worker_runtime import WorkResult


def test_successful_evidenced_work_is_verified():
    proof = evaluate_result(
        WorkResult("face-frame", True, ("artifact://frame.png",)),
        ("execution", "visual-diff"),
    )
    assert proof.verdict is ProofVerdict.VERIFIED
    assert proof.checks == ("execution", "visual-diff")


def test_failed_work_is_rejected():
    proof = evaluate_result(
        WorkResult("train", False, ("artifact://train.log",), "oom"),
        ("execution",),
    )
    assert proof.verdict is ProofVerdict.REJECTED


def test_proof_mesh_requires_checks():
    with pytest.raises(ValueError, match="proof check"):
        evaluate_result(WorkResult("task", True, ("artifact://result",)), ())
