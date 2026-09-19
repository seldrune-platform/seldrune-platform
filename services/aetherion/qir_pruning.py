"""Dead-state pruning for executable Q-IR."""

from __future__ import annotations

from .qir import QIRProgram


def prune_dead_states(program: QIRProgram) -> QIRProgram:
    by_id = {op.op_id: op for op in program.operations}
    if len(by_id) != len(program.operations):
        raise ValueError("duplicate Q-IR operation id")
    required: set[str] = set()
    stack = [program.output_id]
    while stack:
        op_id = stack.pop()
        if op_id in required:
            continue
        op = by_id.get(op_id)
        if op is None:
            raise ValueError("Q-IR dependency does not exist")
        required.add(op_id)
        stack.extend(op.inputs)
    return QIRProgram(
        tuple(op for op in program.operations if op.op_id in required),
        program.output_id,
    )
