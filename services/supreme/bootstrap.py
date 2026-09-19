"""Initial organization backlog consumed by SUPREME HyperSpeed.

This boot graph deliberately advances intelligence and LiveShift in parallel.
"""

from .collaboration import ProjectTask
from .hyperspeed import ExecutionWave, build_execution_waves


def bootstrap_backlog() -> tuple[ProjectTask, ...]:
    return (
        ProjectTask("agi_baseline", "Benchmark current SUPREME capabilities"),
        ProjectTask("agi_experts", "Implement Expert Civilization router"),
        ProjectTask("agi_proof", "Implement Proof Mesh verifier"),
        ProjectTask("agi_forge", "Connect Forge experiment lifecycle"),
        ProjectTask("face_dataset", "Define rights-cleared face training dataset contract"),
        ProjectTask("face_train", "Train Seldrune-owned face model", ("face_dataset",)),
        ProjectTask("face_frame", "Verify real transformed frame", ("face_train",)),
        ProjectTask("face_stream", "Return continuous transformed WebRTC stream", ("face_frame",)),
        ProjectTask("mobile_client", "Build supported mobile LiveShift client", ("face_stream",)),
        ProjectTask(
            "agi_integrate",
            "Integrate verified SUPREME generation",
            ("agi_baseline", "agi_experts", "agi_proof", "agi_forge"),
        ),
    )


def bootstrap_waves() -> tuple[ExecutionWave, ...]:
    return build_execution_waves(bootstrap_backlog())
