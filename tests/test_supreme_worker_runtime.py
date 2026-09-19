import pytest

from services.supreme.collaboration import ProjectTask
from services.supreme.worker_runtime import (
    ResourceKind,
    WorkResult,
    dispatch_order,
    validate_result,
)


def test_face_training_dispatches_to_gpu():
    order = dispatch_order(ProjectTask("face_train", "Train face model"))
    assert order.resource is ResourceKind.GPU
    assert order.accelerator == "rtx-pro-6000-blackwell"


def test_general_engineering_uses_cpu_by_default():
    order = dispatch_order(ProjectTask("agi_router", "Build task router"))
    assert order.resource is ResourceKind.CPU
    assert order.accelerator is None


def test_success_requires_evidence():
    with pytest.raises(ValueError, match="evidence"):
        validate_result(WorkResult("task", True, ()))


def test_failure_requires_error():
    with pytest.raises(ValueError, match="error"):
        validate_result(WorkResult("task", False, ()))
