import pytest

from backend.app.core.config import Settings
from backend.app.services.ai_media_budget import (
    build_media_cost_policy,
    estimate_image_cost_usd,
    estimate_speech_cost_usd,
)


def test_media_policy_uses_live_image_and_speech_apis_with_job_caps() -> None:
    policy = build_media_cost_policy(Settings())

    assert policy.image_model == "gpt-image-2"
    assert policy.image_quality == "low"
    assert policy.image_size == "1024x1024"
    assert policy.image_job_max_usd <= 0.08
    assert policy.speech_model == "gpt-4o-mini-tts"
    assert policy.speech_voice == "marin"
    assert policy.speech_max_chars == 700
    assert policy.speech_job_max_usd <= 0.04
    assert policy.video_available is False


def test_media_policy_tightens_caps_in_conservation_mode() -> None:
    policy = build_media_cost_policy(Settings(), monthly_utilization=0.85)

    assert policy.image_job_max_usd <= 0.04
    assert policy.speech_job_max_usd <= 0.02


def test_media_cost_estimates_are_positive_and_bounded_for_ui_inputs() -> None:
    assert estimate_image_cost_usd(500) == pytest.approx(0.006625)
    assert estimate_speech_cost_usd(700) < 0.04
    assert estimate_speech_cost_usd(0) == 0
