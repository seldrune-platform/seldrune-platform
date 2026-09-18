from dataclasses import dataclass, field


@dataclass
class SessionMetrics:
    frames_in: int = 0
    frames_out: int = 0
    audio_chunks_in: int = 0
    audio_chunks_out: int = 0
    dropped_frames: int = 0
    inference_ms: list[float] = field(default_factory=list)

    def record_inference(self, ms: float) -> None:
        if ms >= 0:
            self.inference_ms.append(ms)

    @property
    def average_inference_ms(self) -> float:
        if not self.inference_ms:
            return 0.0
        return sum(self.inference_ms) / len(self.inference_ms)
