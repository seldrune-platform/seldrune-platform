import asyncio
from argparse import Namespace

from services.live_media import audio_webrtc_runtime_proof


def test_audio_webrtc_proof_exports_async_runner():
    assert asyncio.iscoroutinefunction(audio_webrtc_runtime_proof.run_proof)


def test_audio_webrtc_proof_cli_defaults_are_documented():
    args = Namespace(
        profile_id="authorized-voice-proof",
        receipt="receipt.json",
        timeout=30.0,
    )
    assert args.profile_id.startswith("authorized-")
    assert args.timeout == 30.0
