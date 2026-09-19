"""Consent-gated reference-voice runtime composition for LiveShift."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .aiortc_audio_track import attach_audio_track
from .av_audio_codec import decode_av_audio_frame, encode_av_audio_frame
from .pipeline import LivePipeline
from .processors import AudioProcessor, MediaFrame, VideoProcessor

VoiceReferenceProvider = Callable[[str], object]
VoiceInference = Callable[[object, object], Awaitable[object]]


class ReferenceVoiceProcessor(AudioProcessor):
    """Convert speech using an explicitly enrolled reference voice."""

    def __init__(
        self,
        *,
        reference_provider: VoiceReferenceProvider,
        inference: VoiceInference,
    ) -> None:
        self._reference_provider = reference_provider
        self._inference = inference

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        if not profile_id:
            raise ValueError("authorized voice profile is required")
        reference = self._reference_provider(profile_id)
        if reference is None:
            raise ValueError("enrolled voice reference is required")
        output = await self._inference(frame.payload, reference)
        return MediaFrame(payload=output, timestamp_ms=frame.timestamp_ms)


def build_face_voice_pipeline(
    *,
    video: VideoProcessor,
    face_profile_id: str,
    voice_profile_id: str,
    voice_reference_provider: VoiceReferenceProvider,
    voice_inference: VoiceInference,
) -> LivePipeline:
    if not face_profile_id:
        raise ValueError("authorized face profile is required")
    if not voice_profile_id:
        raise ValueError("authorized voice profile is required")
    return LivePipeline(
        video=video,
        audio=ReferenceVoiceProcessor(
            reference_provider=voice_reference_provider,
            inference=voice_inference,
        ),
        face_profile_id=face_profile_id,
        voice_profile_id=voice_profile_id,
    )


def attach_reference_voice_track(
    peer: object,
    source_track: object,
    pipeline: LivePipeline,
) -> object:
    """Attach the processed voice return track to a WebRTC peer."""
    if not pipeline.voice_profile_id:
        raise ValueError("authorized voice profile is required")
    return attach_audio_track(
        peer,
        source_track,
        pipeline,
        decode_frame=decode_av_audio_frame,
        encode_frame=encode_av_audio_frame,
    )
