"""Dual-track launch plan for Seldrune STI and LiveShift."""

from dataclasses import dataclass

from .bootstrap import bootstrap_backlog
from .collaboration import ProjectTask
from .hyperspeed import ExecutionWave, build_execution_waves


@dataclass(frozen=True)
class DevelopmentProgram:
    name: str
    tasks: tuple[ProjectTask, ...]


def parallel_programs() -> tuple[DevelopmentProgram, ...]:
    tasks = bootstrap_backlog()
    sti = tuple(task for task in tasks if task.task_id.startswith("agi_"))
    liveshift = tuple(task for task in tasks if task.task_id.startswith("face_"))
    liveshift += tuple(task for task in tasks if task.task_id == "mobile_client")
    return (
        DevelopmentProgram("seldrune-sti", sti),
        DevelopmentProgram("liveshift", liveshift),
    )


def combined_execution_waves() -> tuple[ExecutionWave, ...]:
    """Schedule both programs together so independent work starts concurrently."""
    tasks = tuple(task for program in parallel_programs() for task in program.tasks)
    return build_execution_waves(tasks)
