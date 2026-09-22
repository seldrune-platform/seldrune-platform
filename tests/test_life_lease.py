from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from backend.app.models.life_lease import LifeLease
from backend.app.services.life_lease import (
    acquire_life_lease,
    release_life_lease,
    renew_life_lease,
    utcnow,
)


def test_life_lease_api_is_importable() -> None:
    assert callable(acquire_life_lease)
    assert callable(renew_life_lease)
    assert callable(release_life_lease)


def test_life_lease_model_has_single_run_primary_key() -> None:
    primary_keys = [column.name for column in LifeLease.__table__.primary_key.columns]
    assert primary_keys == ["orchestration_run_id"]


def test_life_lease_expiry_is_timezone_aware() -> None:
    expires = utcnow() + timedelta(seconds=120)
    assert expires.tzinfo is not None
    assert uuid4() != uuid4()
