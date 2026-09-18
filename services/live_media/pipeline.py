from dataclasses import dataclass

from .avsync import AVSyncState
from .processors import AudioProcessor, MediaFrame, VideoProcessor


@dataclass
class LivePipeline:
    video: VideoProcessor
    audio: AudioProcessor
    face_profile_id: str | None = None
    voice_profile_id: str | None = None
    sync: AVSyncState | None = None

    def __post_init__(self) -> None:
        if self.sync is None:
            self.sync = AVSyncState()

    async def video_frame(self, frame: MediaFrame) -> MediaFrame:
        assert self.sync is not None
        self.sync.video_ts_ms = frame.timestamp_ms
        if self.face_profile_id:
            return await self.video.process(frame, self.face_profile_id)
        return frame

    async def audio_frame(self, frame: MediaFrame) -> MediaFrame:
        assert self.sync is not None
        self.sync.audio_ts_ms = frame.timestamp_ms
        if self.voice_profile_id:
            return await self.audio.process(frame, self.voice_profile_id)
        return frame
