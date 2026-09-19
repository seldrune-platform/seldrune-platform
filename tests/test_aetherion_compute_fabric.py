from datetime import UTC, datetime

from services.aetherion.compute_fabric import (\n    ComputeClass,\n    build_ephemeral_job,\n    issue_monthly_api_key,\n)


def test_ephemeral_job_does_not_persist_payload():
    job = build_ephemeral_job(b"liveshell-frame")
    assert job.compute_class == ComputeClass.AETHERION_VIRTUAL
    assert not job.persist_payload
    assert len(job.payload_digest) == 64


def test_api_key_expires_after_30_days():
    now = datetime(2026, 9, 19, tzinfo=UTC)
    key = issue_monthly_api_key(now)
    assert key.token.startswith("sel_aeth_")
    assert (key.expires_at - now).days == 30
