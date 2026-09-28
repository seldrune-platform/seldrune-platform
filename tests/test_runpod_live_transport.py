import asyncio
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
    header = {
        "type": "request",
        "media_kind": "video",
        "payload_bytes": MAX_VIDEO_PAYLOAD_BYTES + 1,
    }
    encoded_header = __import__("json").dumps(header).encode()
    reader = asyncio.StreamReader()
    reader.feed_data(len(encoded_header).to_bytes(4, "big") + encoded_header)
    reader.feed_eof()

    with pytest.raises(StreamProtocolError, match="size"):
        asyncio.run(read_message(reader))


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
                "width": 1280,
                "height": 720,
                "fps": 30,
            },
            b"frame",
        )
        video = await read_message(reader)
        assert video.header["type"] == "result"
        assert video.header["synthetic_label_applied"] is True
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
                "channels": 1,
            },
            b"audio",
        )
        audio = await read_message(reader)
        assert audio.header["type"] == "result"
        assert audio.header["timestamp_ms"] == 11
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
        assert audio.payload == b"audio-voice"
        assert audio.timestamp_ms == 21
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
