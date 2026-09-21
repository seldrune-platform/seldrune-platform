from datetime import UTC

from backend.app.models.life_worker_heartbeat import LifeWorkerHeartbeat
from backend.app.services.life_heartbeat import record_worker_heartbeat


def test_worker_heartbeat_model_contract() -> None:
    columns = LifeWorkerHeartbeat.__table__.columns
    assert columns["worker_id"].primary_key
    assert "last_seen_at" in columns
    assert "cycle_count" in columns
    assert "commands_advanced" in columns


def test_heartbeat_service_is_available() -> None:
    assert callable(record_worker_heartbeat)
    assert UTC is not None
