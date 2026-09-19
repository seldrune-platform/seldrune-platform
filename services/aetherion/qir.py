"""Executable Q-IR research representation for Aetherion.

This is a deterministic classical model used to test QGPU ideas. It does not
implement physical quantum computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QIROpcode(StrEnum):
    CONST = "const"
    ADD = "add"
    MUL = "mul"
    XOR = "xor"


@dataclass(frozen=True)
class QIROp:
    op_id: str
    opcode: QIROpcode
    inputs: tuple[str, ...] = ()
    value: int | None = None


@dataclass(frozen=True)
class QIRProgram:
    operations: tuple[QIROp, ...]
    output_id: str


def execute(program: QIRProgram) -> tuple[int, int]:
    values: dict[str, int] = {}
    executed = 0
    for op in program.operations:
        if op.op_id in values:
            raise ValueError("duplicate Q-IR operation id")
        if op.opcode is QIROpcode.CONST:
            if op.value is None:
                raise ValueError("const requires value")
            result = op.value
        else:
            if len(op.inputs) != 2 or any(item not in values for item in op.inputs):
                raise ValueError("operation inputs must already exist")
            left, right = (values[item] for item in op.inputs)
            if op.opcode is QIROpcode.ADD:
                result = left + right
            elif op.opcode is QIROpcode.MUL:
                result = left * right
            else:
                result = left ^ right
        values[op.op_id] = result
        executed += 1
    if program.output_id not in values:
        raise ValueError("Q-IR output does not exist")
    return values[program.output_id], executed
