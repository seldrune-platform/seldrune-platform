"""Constant folding for executable Aetherion Q-IR."""

from __future__ import annotations

from .qir import QIROp, QIROpcode, QIRProgram


def fold_constants(program: QIRProgram) -> QIRProgram:
    constants: dict[str, int] = {}
    folded: list[QIROp] = []
    for op in program.operations:
        if op.opcode is QIROpcode.CONST:
            if op.value is None:
                raise ValueError("const requires value")
            constants[op.op_id] = op.value
            folded.append(op)
            continue
        if len(op.inputs) == 2 and all(item in constants for item in op.inputs):
            left, right = (constants[item] for item in op.inputs)
            if op.opcode is QIROpcode.ADD:
                value = left + right
            elif op.opcode is QIROpcode.MUL:
                value = left * right
            else:
                value = left ^ right
            constants[op.op_id] = value
            folded.append(QIROp(op.op_id, QIROpcode.CONST, value=value))
        else:
            folded.append(op)
    return QIRProgram(tuple(folded), program.output_id)
