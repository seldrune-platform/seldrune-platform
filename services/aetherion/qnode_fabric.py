"""Concurrent QNode research-fabric simulator."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from .qgpu_model import EvidenceLevel
from .qnode import QNodeReport, QNodeRole


@dataclass(frozen=True)
class QNodeFabricReceipt:
    reports: tuple[QNodeReport, ...]
    all_completed: bool
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_nodes_verified: bool = False


def run_parallel(tasks: dict[QNodeRole, Callable[[], int]]) -> QNodeFabricReceipt:
    with ThreadPoolExecutor(max_workers=len(tasks) or 1) as pool:
        futures = {role: pool.submit(task) for role, task in tasks.items()}
        reports = tuple(
            QNodeReport(role, True, future.result())
            for role, future in sorted(futures.items(), key=lambda item: item[0].value)
        )
    return QNodeFabricReceipt(reports, all(item.completed for item in reports))
