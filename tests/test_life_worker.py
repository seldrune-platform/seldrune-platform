from backend.app.core.config import Settings
from backend.app.workers.life_worker import _request_stop, stop_event


def test_life_worker_defaults_are_bounded() -> None:
    settings = Settings()
    assert settings.life_worker_interval_seconds >= 1
    assert 1 <= settings.life_worker_max_commands <= 100
    assert 1 <= settings.life_worker_max_steps_per_command <= 50
    assert 0 <= settings.life_worker_max_retries_per_step <= 2


def test_life_worker_shutdown_signal_sets_stop_event() -> None:
    stop_event.clear()
    _request_stop()
    assert stop_event.is_set()
    stop_event.clear()
