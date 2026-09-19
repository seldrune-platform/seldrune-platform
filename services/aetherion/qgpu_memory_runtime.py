"""Q-Memory integrated execution helper."""

from __future__ import annotations

import hashlib

from .qgpu_kernels import KernelKind, KernelReceipt, run_kernel
from .qmemory_v2 import QMemoryV2


def execute_cached(
    memory: QMemoryV2,
    kind: KernelKind,
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> KernelReceipt:
    raw = repr((kind.value, left, right)).encode()
    key = hashlib.sha256(raw).hexdigest()
    cached = memory.get(key)
    if cached is not None:
        values = tuple(float(item) for item in cached.decode().split(",") if item)
        return KernelReceipt(kind, values, 0)
    receipt = run_kernel(kind, left, right)
    memory.put(key, ",".join(map(str, receipt.output)).encode())
    return receipt
