from dataclasses import dataclass
from math import ceil

from backend.app.core.config import Settings


@dataclass(frozen=True)
class MediaCostPolicy:
    image_model: str
    image_quality: str
    image_size: str
    image_job_max_usd: float
    speech_model: str
    speech_voice: str
    speech_max_chars: int
    speech_job_max_usd: float
    video_available: bool


def build_media_cost_policy(
    settings: Settings,
    *,
    monthly_utilization: float = 0.0,
) -> MediaCostPolicy:
    """Return capped settings for media types backed by live provider APIs."""
    conservation = float(monthly_utilization) >= settings.ai_conservation_ratio
    image_budget = min(
        settings.ai_image_job_max_usd,
        0.04 if conservation else settings.ai_image_job_max_usd,
    )
    speech_budget = min(
        settings.ai_request_max_usd,
        0.02 if conservation else 0.04,
    )
    return MediaCostPolicy(
        image_model="gpt-image-2",
        image_quality="low",
        image_size="1024x1024",
        image_job_max_usd=image_budget,
        speech_model="gpt-4o-mini-tts",
        speech_voice="marin",
        speech_max_chars=700,
        speech_job_max_usd=speech_budget,
        video_available=False,
    )


def estimate_image_cost_usd(prompt_chars: int) -> float:
    """Estimate a low-quality 1024px image plus prompt processing cost."""
    prompt_tokens = ceil(max(int(prompt_chars), 0) / 4)
    return round(0.006 + prompt_tokens * 5 / 1_000_000, 8)


def estimate_speech_cost_usd(text_chars: int) -> float:
    """Estimate TTS cost from text and conservatively estimated audio tokens."""
    characters = max(int(text_chars), 0)
    input_tokens = ceil(characters / 4)
    audio_tokens = characters * 4
    return round(input_tokens * 0.60 / 1_000_000 + audio_tokens * 12 / 1_000_000, 8)
