from dataclasses import dataclass, field

@dataclass
class SessionMetrics:
    frames_in:int=0
    frames_out:int=0
    audio_chunks_in:int=0
    audio_chunks_out:int=0
    dropped_frames:int=0
    inference_ms:list[float]=field(default_factory=list)

    def record_inference(self,ms:float):
        if ms>=0: self.inference_ms.append(ms)

    @property
    def average_inference_ms(self)->float:
        return sum(self.inference_ms)/len(self.inference_ms) if self.inference_ms else 0.0
