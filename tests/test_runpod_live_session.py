import asyncio
import ssl

import pytest

from services.live_media.processors import MediaFrame
from services.live_media.runpod_live_session import RunPodLiveSession
from services.live_media.worker_protocol import InferenceRequest, InferenceResult, MediaKind


class FakeRunPodClient:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []
        self.closed = False

    async def __call__(
        self, _worker: object, request: InferenceRequest
    ) -> InferenceResult:
        self.requests.append(request)
        metadata = (
            {
                "width": request.width,
                "height": request.height,
                "fps": request.fps,
            }
            if request.media_kind == MediaKind.VIDEO
            else {
                "sample_rate_hz": request.sample_rate_hz,
                "channels": request.channels,
            }
        )
        return InferenceResult(
            request_id=request.request_id,
            timestamp_ms=request.timestamp_ms,
            payload=b"transformed:" + request.payload,
            inference_ms=2.0,
            **metadata,
        )

    async def close(self) -> None:
        self.closed = True


def test_session_uses_one_authenticated_client_for_bound_av_pipeline():
    async def scenario() -> None:
        client = FakeRunPodClient()
        factory_calls = []

        async def connect_client(host, port, **kwargs):
            factory_calls.append((host, port, kwargs))
            return client

        session = await RunPodLiveSession.connect(
            host="worker.internal",
            port=8765,
            service_token="worker-token",
            ticket="signed-session-ticket",
            session_id="session-1",
            face_profile_id="face-profile",
            voice_profile_id="voice-profile",
            region="us-east",
            ssl_context=ssl.create_default_context(),
            server_hostname="worker.internal",
            max_inflight=2,
            client_factory=connect_client,
        )
        video, audio = await asyncio.gather(
            session.video_frame(
                MediaFrame(
                    b"portrait-frame",
                    1000,
                    width=1080,
                    height=1920,
                    fps=7500 / 253,
                )
            ),
            session.audio_frame(
                MediaFrame(
                    b"stereo-chunk",
                    1010,
                    sample_rate_hz=48000,
                    channels=2,
                )
            ),
        )

        assert len(factory_calls) == 1
        assert factory_calls[0][0:2] == ("worker.internal", 8765)
        assert factory_calls[0][2]["ticket"] == "signed-session-ticket"
        assert video.payload == b"transformed:portrait-frame"
        assert (video.width, video.height) == (1080, 1920)
        assert video.fps == pytest.approx(7500 / 253)
        assert audio.payload == b"transformed:stereo-chunk"
        assert (audio.sample_rate_hz, audio.channels) == (48000, 2)
        assert [request.profile_id for request in client.requests] == [
            "face-profile",
            "voice-profile",
        ]
        assert {request.session_id for request in client.requests} == {"session-1"}

        await session.close()
        await session.close()
        assert client.closed is True
        with pytest.raises(RuntimeError, match="closed"):
            await session.video_frame(MediaFrame(b"late", 2000))

    asyncio.run(scenario())


def test_session_rejects_more_inflight_requests_than_worker_contract():
    async def scenario() -> None:
        called = False

        async def connect_client(*_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("invalid capacity must fail before connecting")

        with pytest.raises(ValueError, match="one or two"):
            await RunPodLiveSession.connect(
                host="worker.internal",
                port=8765,
                service_token="worker-token",
                ticket="signed-session-ticket",
                session_id="session-1",
                face_profile_id="face-profile",
                voice_profile_id="voice-profile",
                region="us-east",
                ssl_context=ssl.create_default_context(),
                server_hostname="worker.internal",
                max_inflight=3,
                client_factory=connect_client,
            )
        assert called is False

    asyncio.run(scenario())
