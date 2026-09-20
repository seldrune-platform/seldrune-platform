"""Combined consent-gated Face + Voice WebRTC runtime composition."""

from __future__ import annotations

from .aiortc_audio_track import attach_audio_track
from .aiortc_video_track import attach_video_track
from .av_audio_codec import decode_av_audio_frame, encode_av_audio_frame
from .av_video_codec import decode_av_video_frame, encode_av_video_frame
from .model_adapters import AuthorizedFaceAdapter
from .pipeline import LivePipeline
from .reference_runtime import ReferenceTensorOnnxBackend
from .reference_voice_runtime import (
    ReferenceVoiceProcessor,
    VoiceInference,
    VoiceReferenceProvider,
)


def build_reference_av_pipeline(
    face_session: object,
    *,
    face_profile_id: str,
    face_reference_provider,
    voice_profile_id: str,
    voice_reference_provider: VoiceReferenceProvider,
    voice_inference: VoiceInference,
) -> LivePipeline:
    """Build one shared A/V pipeline so audio and video share sync state."""
    if not face_profile_id or not voice_profile_id:
        raise ValueError("authorized face and voice profiles are required")
    face_backend = ReferenceTensorOnnxBackend(
        face_session,
        reference_provider=face_reference_provider,
    )
    return LivePipeline(
        video=AuthorizedFaceAdapter(face_backend),
        audio=ReferenceVoiceProcessor(
            reference_provider=voice_reference_provider,
            inference=voice_inference,
        ),
        face_profile_id=face_profile_id,
        voice_profile_id=voice_profile_id,
    )


def attach_reference_av_tracks(
    peer: object,
    *,
    video_track: object,
    audio_track: object,
    pipeline: LivePipeline,
    metadata_observer: object | None = None,
) -> tuple[object, object]:
    """Attach transformed video and audio tracks backed by one sync state."""
    if not pipeline.face_profile_id or not pipeline.voice_profile_id:
        raise ValueError("authorized face and voice profiles are required")
    returned_video = attach_video_track(
        peer,
        video_track,
        pipeline,
        decode_frame=decode_av_video_frame,
        encode_frame=encode_av_video_frame,
        metadata_observer=metadata_observer,
    )
    returned_audio = attach_audio_track(
        peer,
        audio_track,
        pipeline,
        decode_frame=decode_av_audio_frame,
        encode_frame=encode_av_audio_frame,
        metadata_observer=metadata_observer,
    )
    return returned_video, returned_audio
