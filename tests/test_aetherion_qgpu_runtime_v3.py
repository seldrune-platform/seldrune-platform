from services.aetherion.qgpu_graphics import shade_lambert
from services.aetherion.qgpu_model import WorkloadDomain
from services.aetherion.qgpu_runtime_v3 import execute
from services.aetherion.qgpu_scientific import diffusion_step
from services.aetherion.qgpu_tensor import matmul


def test_tensor_kernel():
    result = matmul(((1.0, 2.0),), ((3.0,), (4.0,)))
    assert result.output == ((11.0,),)
    assert not result.hardware_benchmark


def test_graphics_kernel():
    result = shade_lambert((1.0, 0.5), (0.8, -0.2))
    assert result.pixels == (0.8, 0.0)
    assert not result.physical_graphics_hardware_verified


def test_scientific_kernel():
    result = diffusion_step((0.0, 1.0, 0.0))
    assert result.output == (0.0, 0.8, 0.0)


def test_runtime_v3_dispatches_all_domains_without_hardware_claims():
    for domain in WorkloadDomain:
        result = execute(domain, (1.0, 0.0), (2.0, 3.0))
        assert result.dispatch.domain is domain
        assert not result.physical_quantum_hardware_verified
        assert not result.quantum_speedup_verified
