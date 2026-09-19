"""Traceback Intelligence: recursive evidence graph for STI work."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceNode:
    node_id: str
    task_id: str
    parent_id: str | None
    evidence: tuple[str, ...] = ()
    confidence: float = 0.0


def validate_trace(nodes: tuple[TraceNode, ...]) -> None:
    by_id = {node.node_id: node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("trace node ids must be unique")
    for node in nodes:
        if not 0.0 <= node.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if node.parent_id is not None and node.parent_id not in by_id:
            raise ValueError(f"unknown parent: {node.parent_id}")

    for start in nodes:
        seen: set[str] = set()
        current: TraceNode | None = start
        while current is not None:
            if current.node_id in seen:
                raise ValueError("traceback cycle detected")
            seen.add(current.node_id)
            current = by_id.get(current.parent_id) if current.parent_id else None


def trace_lineage(nodes: tuple[TraceNode, ...], node_id: str) -> tuple[TraceNode, ...]:
    validate_trace(nodes)
    by_id = {node.node_id: node for node in nodes}
    if node_id not in by_id:
        raise ValueError("unknown trace node")
    lineage: list[TraceNode] = []
    current: TraceNode | None = by_id[node_id]
    while current is not None:
        lineage.append(current)
        current = by_id.get(current.parent_id) if current.parent_id else None
    return tuple(lineage)
