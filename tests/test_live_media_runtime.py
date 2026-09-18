from services.live_media.avsync import AVSyncState
from services.live_media.gpu_scheduler import GPUWorker, choose_worker

def test_avsync():
    assert AVSyncState(audio_ts_ms=1000,video_ts_ms=950).correction()=="none"
    assert AVSyncState(audio_ts_ms=1100,video_ts_ms=950).correction()=="delay_video"

def test_region_preferred():
    a=GPUWorker("a","us")
    b=GPUWorker("b","in")
    assert choose_worker([a,b],"in").worker_id=="b"
