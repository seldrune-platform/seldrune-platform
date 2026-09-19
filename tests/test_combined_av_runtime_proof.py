import asyncio

from services.live_media import combined_av_runtime_proof


def test_combined_av_runtime_proof_exports_async_runner():
    assert asyncio.iscoroutinefunction(combined_av_runtime_proof.run_proof)
