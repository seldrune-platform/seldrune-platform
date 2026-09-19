from services.aetherion.qgpu_benchmark_v2 import run_benchmark
from services.aetherion.qgpu_device_interface import DeviceMode, current_capabilities
from services.aetherion.qgpu_kernels import KernelKind, run_kernel
from services.aetherion.qgpu_memory_runtime import execute_cached
from services.aetherion.qgpu_state_space import reduce_state_space
from services.aetherion.qmemory_v2 import QMemoryV2


def test_universal_kernels_execute():
    result = run_kernel(KernelKind.VECTOR_ADD, (1.0, 2.0), (3.0, 4.0))
    assert result.output == (4.0, 6.0)
    assert not result.hardware_benchmark


def test_state_space_reduction_is_evidence_gated():
    result = reduce_state_space(100, 20, 30)
    assert result.surviving_states == 50
    assert not result.physical_superposition_verified


def test_qmemory_eliminates_repeated_kernel_work():
    memory = QMemoryV2()
    first = execute_cached(memory, KernelKind.DOT_PRODUCT, (1.0, 2.0), (3.0, 4.0))
    second = execute_cached(memory, KernelKind.DOT_PRODUCT, (1.0, 2.0), (3.0, 4.0))
    assert first.output == second.output
    assert second.operations == 0


def test_cross_domain_benchmark_remains_software_only():
    result = run_benchmark(32)
    assert len(result.cases) == 4
    assert not result.hardware_benchmark
    assert not result.quantum_speedup_verified


def test_device_boundary_does_not_claim_unbuilt_hardware():
    capabilities = {item.mode: item for item in current_capabilities()}
    assert capabilities[DeviceMode.CLASSICAL_SIMULATOR].executable
    assert not capabilities[DeviceMode.FPGA_EMULATION].verified
    assert not capabilities[DeviceMode.PHYSICAL_QGPU].verified
