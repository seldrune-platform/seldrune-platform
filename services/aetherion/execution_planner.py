"""Compatibility import for the superseded execution-planner prototype.

Aetherion QGPU is now modeled in qgpu_model. This module remains temporarily
so older imports fail gracefully while the research branch migrates.
"""

from .qgpu_model import (
    EvidenceLevel,
    QGPUPlan,
    QGPUWorkload,
    QuantumExecutionField,
    WorkloadDomain,
    compile_qgpu_plan,
    construct_execution_field,
)

__all__ = (
    "EvidenceLevel",
    "QGPUPlan",
    "QGPUWorkload",
    "QuantumExecutionField",
    "WorkloadDomain",
    "compile_qgpu_plan",
    "construct_execution_field",
)
