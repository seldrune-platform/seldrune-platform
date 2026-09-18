from dataclasses import dataclass
from .processors import MediaFrame,VideoProcessor,AudioProcessor
from .avsync import AVSyncState

@dataclass
class LivePipeline:
    video:VideoProcessor
    audio:AudioProcessor
    face_profile_id:str|None=None
    voice_profile_id:str|None=None
    sync:AVSyncState=None

    def __post_init__(self):
        if self.sync is None: self.sync=AVSyncState()

    async def video_frame(self,frame:MediaFrame)->MediaFrame:
        self.sync.video_ts_ms=frame.timestamp_ms
        return await self.video.process(frame,self.face_profile_id) if self.face_profile_id else frame

    async def audio_frame(self,frame:MediaFrame)->MediaFrame:
        self.sync.audio_ts_ms=frame.timestamp_ms
        return await self.audio.process(frame,self.voice_profile_id) if self.voice_profile_id else frame
