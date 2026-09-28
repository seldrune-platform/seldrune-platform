import asyncio
import json
import ssl
from time import time

import pytest

from services.live_media.runpod_live_transport import (
    MAX_VIDEO_PAYLOAD_BYTES,
    RunPodLiveWorkerClient,
    RunPodLiveWorkerServer,
    SessionTicketClaims,
    StreamProtocolError,
    encode_message,
    issue_session_ticket,
    read_message,
    verify_session_ticket,
    write_message,
)
from services.live_media.worker_protocol import InferenceRequest, MediaKind

from services.live_media.realism_quality_gate import (
    FaceRealismEvidence,
    FaceTransformOutput,
    RealismQualityPolicy,
    VoiceRealismEvidence,
    VoiceTransformOutput,
)

SIGNING_SECRET = "s" * 48
SERVICE_TOKEN = "w" * 40


def make_claims(*, now=None, face_consent=True, voice_consent=True, indicator=True):
    issued_at = int(time()) if now is None else now
    return SessionTicketClaims(
        organization_id="org-test",
        user_id="user-test",
        session_id="session-test",
        face_profile_id="face-test",
        voice_profile_id="voice-test",
        issued_at=issued_at,
        expires_at=issued_at + 600,
        face_consent_verified=face_consent,
        voice_consent_verified=voice_consent,
        synthetic_media_indicator_enabled=indicator,
    )


def test_session_ticket_is_short_lived_and_binds_both_profiles():
    now = int(time())
    ticket = issue_session_ticket(make_claims(now=now), SIGNING_SECRET)
    claims = verify_session_ticket(ticket, SIGNING_SECRET, now=now + 5)
    assert claims.session_id == "session-test"
    assert claims.face_profile_id == "face-test"
    assert claims.voice_profile_id == "voice-test"

    with pytest.raises(StreamProtocolError, match="signature"):
        verify_session_ticket(ticket, "x" * 48, now=now + 5)
    with pytest.raises(StreamProtocolError, match="expired"):
        verify_session_ticket(ticket, SIGNING_SECRET, now=now + 601)


@pytest.mark.parametrize(
    "claims",
    [
        make_claims(face_consent=False),
        make_claims(voice_consent=False),
        make_claims(indicator=False),
    ],
)
def test_ticket_cannot_be_issued_without_face_voice_and_disclosure_gates(claims):
    with pytest.raises(StreamProtocolError, match="consent"):
        issue_session_ticket(claims, SIGNING_SECRET)


def test_video_payload_limit_is_checked_before_network_read():
    async def scenario():
        header = {
            "type": "request",
            "media_kind": "video",
            "payload_bytes": MAX_VIDEO_PAYLOAD_BYTES + 1,
        }
        encoded_header = json.dumps(header).encode()
        reader = asyncio.StreamReader()
        reader.feed_data(len(encoded_header).to_bytes(4, "big") + encoded_header)
        reader.feed_eof()

        with pytest.raises(StreamProtocolError, match="size"):
            await read_message(reader)

    asyncio.run(scenario())


def test_control_messages_round_trip_with_binary_video_payload():
    async def scenario():
        reader = asyncio.StreamReader()
        packet = encode_message(
            {"type": "request", "media_kind": "video", "request_id": "f1"},
            b"jpeg-frame",
        )
        reader.feed_data(packet)
        reader.feed_eof()
        message = await read_message(reader)
        assert message.header["request_id"] == "f1"
        assert message.payload == b"jpeg-frame"

    asyncio.run(scenario())


def test_worker_round_trips_labeled_video_and_transformed_voice():
    async def transform_face(payload, profile_id):
        return payload + b":" + profile_id.encode()

    async def transform_voice(payload, profile_id):
        return payload + b":" + profile_id.encode()

    async def label_video(payload):
        return b"AI-SYNTHETIC|" + payload

    async def scenario():
        worker = RunPodLiveWorkerServer(
            service_token=SERVICE_TOKEN,
            ticket_secret=SIGNING_SECRET,
            transform_face=transform_face,
            transform_voice=transform_voice,
            label_synthetic_video=label_video,
            actual_accelerator_profile="rtx-4090",
        )
        server = await asyncio.start_server(worker.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        ticket = issue_session_ticket(make_claims(), SIGNING_SECRET)
        await write_message(
            writer,
            {
                "type": "hello",
                "service_token": SERVICE_TOKEN,
                "ticket": ticket,
                "session_id": "session-test",
            },
        )
        ready = await read_message(reader)
        assert ready.header["type"] == "ready"
        assert ready.header["actual_accelerator_profile"] == "rtx-4090"

        await write_message(
            writer,
            {
                "type": "request",
                "request_id": "video-1",
                "session_id": "session-test",
                "media_kind": "video",
                "profile_id": "face-test",
                "timestamp_ms": 10,
                "sequence": 1,
                "width": 1080,
                "height": 1920,
                "fps": 7500 / 253,
            },
            b"frame",
        )
        video = await read_message(reader)
        assert video.header["type"] == "result"
        assert video.header["synthetic_label_applied"] is True
        assert (video.header["width"], video.header["height"]) == (1080, 1920)
        assert video.header["fps"] == pytest.approx(7500 / 253)
        assert video.payload == b"AI-SYNTHETIC|frame:face-test"

        await write_message(
            writer,
            {
                "type": "request",
                "request_id": "audio-1",
                "session_id": "session-test",
                "media_kind": "audio",
                "profile_id": "voice-test",
                "timestamp_ms": 11,
                "sequence": 1,
                "sample_rate_hz": 48000,
                "channels": 2,
            },
            b"audio",
        )
        audio = await read_message(reader)
        assert audio.header["type"] == "result"
        assert audio.header["timestamp_ms"] == 11
        assert (audio.header["sample_rate_hz"], audio.header["channels"]) == (48000, 2)
        assert audio.payload == b"audio:voice-test"

        writer.close()
        await writer.wait_closed()

        replay_reader, replay_writer = await asyncio.open_connection(
            "127.0.0.1", port
        )
        await write_message(
            replay_writer,
            {
                "type": "hello",
                "service_token": SERVICE_TOKEN,
                "ticket": ticket,
                "session_id": "session-test",
            },
        )
        replay = await read_message(replay_reader)
        assert replay.header["type"] == "error"
        replay_writer.close()
        await replay_writer.wait_closed()

        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_worker_rejects_profile_mismatch_before_transforming():
    async def transform(payload, _profile):
        return payload + b"-changed"

    async def scenario():
        worker = RunPodLiveWorkerServer(
            service_token=SERVICE_TOKEN,
            ticket_secret=SIGNING_SECRET,
            transform_face=transform,
            transform_voice=transform,
            label_synthetic_video=transform,
        )
        server = await asyncio.start_server(worker.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        ticket = issue_session_ticket(make_claims(), SIGNING_SECRET)
        await write_message(
            writer,
            {
                "type": "hello",
                "service_token": SERVICE_TOKEN,
                "ticket": ticket,
                "session_id": "session-test",
            },
        )
        await read_message(reader)
        await write_message(
            writer,
            {
                "type": "request",
                "request_id": "wrong-profile",
                "session_id": "session-test",
                "media_kind": "video",
                "profile_id": "someone-else",
                "timestamp_ms": 10,
                "sequence": 1,
                "width": 1280,
                "height": 720,
                "fps": 30,
            },
            b"frame",
        )
        error = await read_message(reader)
        assert error.header["type"] == "error"
        assert error.header["code"] == "invalid_live_request"

        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_multiplexed_client_correlates_audio_and_video_results():
    async def transform_face(payload, _profile):
        await asyncio.sleep(0.01)
        return payload + b"-face"

    async def transform_voice(payload, _profile):
        await asyncio.sleep(0.001)
        return payload + b"-voice"

    async def label_video(payload):
        return b"AI-SYNTHETIC|" + payload

    async def scenario():
        worker = RunPodLiveWorkerServer(
            service_token=SERVICE_TOKEN,
            ticket_secret=SIGNING_SECRET,
            transform_face=transform_face,
            transform_voice=transform_voice,
            label_synthetic_video=label_video,
        )
        server = await asyncio.start_server(worker.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        ticket = issue_session_ticket(make_claims(), SIGNING_SECRET)
        await write_message(
            writer,
            {
                "type": "hello",
                "service_token": SERVICE_TOKEN,
                "ticket": ticket,
                "session_id": "session-test",
            },
        )
        assert (await read_message(reader)).header["type"] == "ready"
        client = RunPodLiveWorkerClient(
            reader, writer, session_id="session-test", max_inflight=2
        )
        video, audio = await asyncio.gather(
            client.infer(
                InferenceRequest(
                    request_id="client-video",
                    session_id="session-test",
                    media_kind=MediaKind.VIDEO,
                    profile_id="face-test",
                    timestamp_ms=20,
                    payload=b"frame",
                )
            ),
            client.infer(
                InferenceRequest(
                    request_id="client-audio",
                    session_id="session-test",
                    media_kind=MediaKind.AUDIO,
                    profile_id="voice-test",
                    timestamp_ms=21,
                    payload=b"audio",
                )
            ),
        )
        assert video.payload == b"AI-SYNTHETIC|frame-face"
        assert video.timestamp_ms == 20
        assert (video.width, video.height, video.fps) == (1280, 720, 30.0)
        assert audio.payload == b"audio-voice"
        assert audio.timestamp_ms == 21
        assert (audio.sample_rate_hz, audio.channels) == (48000, 1)
        await client.close()
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_server_refuses_to_start_without_tls():
    worker = RunPodLiveWorkerServer(
        service_token=SERVICE_TOKEN,
        ticket_secret=SIGNING_SECRET,
        transform_face=lambda *_: None,
        transform_voice=lambda *_: None,
        label_synthetic_video=lambda *_: None,
    )
    with pytest.raises(ValueError, match="TLS"):
        asyncio.run(worker.serve("0.0.0.0", 9000, ssl_context=None))


def test_strict_worker_requires_and_returns_realism_evidence():
    quality_policy = RealismQualityPolicy(
        face_min_identity_similarity=0.8,
        face_min_temporal_consistency=0.8,
        face_min_blend_quality=0.8,
        voice_min_speaker_similarity=0.8,
        voice_min_content_preservation=0.9,
        voice_min_naturalness=0.75,
        voice_max_clipped_fraction=0.001,
        voice_max_dropout_fraction=0.001,
        max_processing_p95_ms=150.0,
        max_av_drift_ms=80.0,
    )

    async def transform_face(payload, _profile):
        return FaceTransformOutput(
            payload=payload + b"-face",
            evidence=FaceRealismEvidence(
                evaluator_id="face-eval",
                evaluator_version="test-1",
                window_frames=30,
                output_width=1280,
                output_height=720,
                output_fps=30.0,
                identity_similarity=0.92,
                temporal_consistency=0.91,
                blend_quality=0.88,
                p95_inference_ms=110.0,
            ),
        )

    async def transform_voice(payload, _profile):
        return VoiceTransformOutput(
            payload=payload + b"-voice",
            evidence=VoiceRealismEvidence(
                evaluator_id="voice-eval",
                evaluator_version="test-1",
                window_duration_seconds=1.2,
                sample_rate_hz=48000,
                channels=1,
                speaker_similarity=0.9,
                content_preservation=0.96,
                naturalness=0.84,
                clipped_fraction=0.0001,
                dropout_fraction=0.0002,
                p95_processing_ms=120.0,
            ),
        )

    async def label_video(payload):
        return b"AI-SYNTHETIC|" + payload

    async def scenario():
        worker = RunPodLiveWorkerServer(
            service_token=SERVICE_TOKEN,
            ticket_secret=SIGNING_SECRET,
            transform_face=transform_face,
            transform_voice=transform_voice,
            label_synthetic_video=label_video,
            realism_policy=quality_policy,
            require_realism_evidence=True,
        )
        server = await asyncio.start_server(worker.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        ticket = issue_session_ticket(make_claims(), SIGNING_SECRET)
        await write_message(
            writer,
            {
                "type": "hello",
                "service_token": SERVICE_TOKEN,
                "ticket": ticket,
                "session_id": "session-test",
            },
        )
        ready = await read_message(reader)
        assert ready.header["realism_evidence_required"] is True

        client = RunPodLiveWorkerClient(
            reader,
            writer,
            session_id="session-test",
            max_inflight=2,
            require_realism_evidence=True,
        )
        video, audio = await asyncio.gather(
            client.infer(
                InferenceRequest(
                    request_id="quality-video",
                    session_id="session-test",
                    media_kind=MediaKind.VIDEO,
                    profile_id="face-test",
                    timestamp_ms=100,
                    payload=b"frame",
                    sequence=1,
                    width=1280,
                    height=720,
                    fps=30,
                )
            ),
            client.infer(
                InferenceRequest(
                    request_id="quality-audio",
                    session_id="session-test",
                    media_kind=MediaKind.AUDIO,
                    profile_id="voice-test",
                    timestamp_ms=110,
                    payload=b"audio",
                    sequence=1,
                    sample_rate_hz=48000,
                    channels=1,
                )
            ),
        )
        assert video.quality_evidence["media_kind"] == "video"
        assert video.payload == b"AI-SYNTHETIC|frame-face"
        assert (video.width, video.height, video.fps) == (1280, 720, 30.0)
        assert audio.quality_evidence["evaluator_id"] == "voice-eval"
        assert audio.payload == b"audio-voice"
        assert (audio.sample_rate_hz, audio.channels) == (48000, 1)
        await client.close()
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_strict_worker_rejects_audio_video_drift_before_face_inference():
    quality_policy = RealismQualityPolicy(
        face_min_identity_similarity=0.8,
        face_min_temporal_consistency=0.8,
        face_min_blend_quality=0.8,
        voice_min_speaker_similarity=0.8,
        voice_min_content_preservation=0.9,
        voice_min_naturalness=0.75,
        voice_max_clipped_fraction=0.001,
        voice_max_dropout_fraction=0.001,
        max_processing_p95_ms=150.0,
        max_av_drift_ms=80.0,
    )
    face_called = False

    async def transform_face(payload, _profile):
        nonlocal face_called
        face_called = True
        return FaceTransformOutput(
            payload=payload,
            evidence=FaceRealismEvidence(
                evaluator_id="face-eval",
                evaluator_version="test-1",
                window_frames=30,
                output_width=1280,
                output_height=720,
                output_fps=30.0,
                identity_similarity=0.92,
                temporal_consistency=0.91,
                blend_quality=0.88,
                p95_inference_ms=110.0,
            ),
        )

    async def transform_voice(payload, _profile):
        return VoiceTransformOutput(
            payload=payload,
            evidence=VoiceRealismEvidence(
                evaluator_id="voice-eval",
                evaluator_version="test-1",
                window_duration_seconds=1.2,
                sample_rate_hz=48000,
                channels=1,
                speaker_similarity=0.9,
                content_preservation=0.96,
                naturalness=0.84,
                clipped_fraction=0.0001,
                dropout_fraction=0.0002,
                p95_processing_ms=120.0,
            ),
        )

    async def label_video(payload):
        return payload

    async def scenario():
        worker = RunPodLiveWorkerServer(
            service_token=SERVICE_TOKEN,
            ticket_secret=SIGNING_SECRET,
            transform_face=transform_face,
            transform_voice=transform_voice,
            label_synthetic_video=label_video,
            realism_policy=quality_policy,
            require_realism_evidence=True,
        )
        server = await asyncio.start_server(worker.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        await write_message(
            writer,
            {
                "type": "hello",
                "service_token": SERVICE_TOKEN,
                "ticket": issue_session_ticket(make_claims(), SIGNING_SECRET),
                "session_id": "session-test",
            },
        )
        assert (await read_message(reader)).header["type"] == "ready"
        await write_message(
            writer,
            {
                "type": "request",
                "request_id": "sync-audio",
                "session_id": "session-test",
                "media_kind": "audio",
                "profile_id": "voice-test",
                "timestamp_ms": 1000,
                "sequence": 1,
                "sample_rate_hz": 48000,
                "channels": 1,
            },
            b"audio",
        )
        assert (await read_message(reader)).header["type"] == "result"
        await write_message(
            writer,
            {
                "type": "request",
                "request_id": "late-video",
                "session_id": "session-test",
                "media_kind": "video",
                "profile_id": "face-test",
                "timestamp_ms": 900,
                "sequence": 1,
                "width": 1280,
                "height": 720,
                "fps": 30,
            },
            b"frame",
        )
        error = await read_message(reader)
        assert error.header["type"] == "error"
        assert error.header["code"] == "av_sync_threshold_exceeded"
        assert face_called is False
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_client_rejects_tls_without_hostname_verification():
    context = ssl.create_default_context()
    context.check_hostname = False

    async def scenario():
        with pytest.raises(ValueError, match="verified TLS"):
            await RunPodLiveWorkerClient.connect(
                "worker.invalid",
                8765,
                service_token=SERVICE_TOKEN,
                ticket="signed-session-ticket",
                session_id="session-test",
                ssl_context=context,
                server_hostname="worker.invalid",
            )

    asyncio.run(scenario())
